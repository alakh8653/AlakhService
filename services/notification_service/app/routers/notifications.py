import asyncio
import json

import redis.asyncio as aioredis
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Response, WebSocket
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import NotificationNotFoundError, NotificationServiceError, TemplateNotFoundError
from app.database import get_db
from app.dependencies import (
    Caller,
    caller_from_token,
    ensure_self_or_admin,
    require_admin,
    require_caller,
    target_user,
)
from app.models.notification import DeviceToken, NotificationTemplate
from app.schemas.notification import (
    DeviceTokenCreate,
    DeviceTokenRemove,
    DeviceTokenResponse,
    NotificationCreate,
    NotificationListResponse,
    NotificationResponse,
    NotificationTemplateCreate,
    NotificationTemplateResponse,
)
from app.services.notification_service import notification_service
from app.services.template_service import template_service

router = APIRouter()
log = structlog.get_logger()


class WSConnectionManager:
    def __init__(self):
        self.connections: dict[str, list[WebSocket]] = {}

    async def connect(self, user_id: str, ws: WebSocket):
        await ws.accept()
        self.connections.setdefault(user_id, []).append(ws)

    def disconnect(self, user_id: str, ws: WebSocket):
        if user_id in self.connections:
            try:
                self.connections[user_id].remove(ws)
            except ValueError:
                pass

    async def send(self, user_id: str, data: dict):
        for ws in self.connections.get(user_id, []):
            try:
                await ws.send_json(data)
            except Exception:
                pass


ws_manager = WSConnectionManager()


async def get_redis():
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        yield r
    finally:
        await r.aclose()


# Sending is for platform services and operators, not end users.
@router.post(
    "/notifications/send",
    response_model=NotificationResponse,
    status_code=201,
    dependencies=[Depends(require_admin)],
)
async def send_notification(
    payload: NotificationCreate,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    try:
        notif = await notification_service.send(
            db,
            redis,
            payload.user_id,
            payload.template_name,
            payload.variables,
            payload.channels,
            payload.priority,
        )
        return notif
    except TemplateNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except NotificationServiceError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/notifications/me", response_model=NotificationListResponse)
async def get_my_notifications(
    user_id: str = Depends(target_user),
    unread_only: bool = Query(False),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await notification_service.get_notifications(db, user_id, unread_only, page, per_page)


@router.post("/notifications/{notification_id}/read")
async def mark_read(
    notification_id: str,
    user_id: str = Depends(target_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await notification_service.mark_as_read(db, notification_id, user_id)
        return {"success": True}
    except NotificationNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/notifications/read-all")
async def mark_all_read(
    user_id: str = Depends(target_user),
    db: AsyncSession = Depends(get_db),
):
    count = await notification_service.mark_all_read(db, user_id)
    return {"marked_read": count}


@router.get("/notifications/count/unread")
async def unread_count(
    user_id: str = Depends(target_user),
    db: AsyncSession = Depends(get_db),
):
    count = await notification_service.get_unread_count(db, user_id)
    return {"unread_count": count}


@router.websocket("/ws/notifications/{user_id}")
async def ws_notifications(websocket: WebSocket, user_id: str, token: str = Query(...)):
    # Browsers cannot set headers on a WebSocket handshake, so the access token comes as ?token=.
    try:
        ensure_self_or_admin(user_id, caller_from_token(token))
    except HTTPException:
        await websocket.close(code=1008)
        return
    await ws_manager.connect(user_id, websocket)
    channel = f"notifications:{user_id}"
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe(channel)

    async def forward_notifications():
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            try:
                data = json.loads(message["data"])
            except ValueError:
                log.warning("ws_notification_not_json", user_id=user_id)
                continue
            # A failed send means the socket is gone; let it end the connection.
            await websocket.send_json(data)

    async def wait_for_disconnect():
        # Clients send nothing we use, but only reading the socket reveals that they left.
        while (await websocket.receive())["type"] != "websocket.disconnect":
            pass

    forward = asyncio.create_task(forward_notifications())
    client = asyncio.create_task(wait_for_disconnect())
    try:
        await asyncio.wait({forward, client}, return_when=asyncio.FIRST_COMPLETED)
        if forward.done() and not forward.cancelled() and forward.exception():
            log.warning("ws_notification_forward_failed", user_id=user_id, error=str(forward.exception()))
        if not client.done():
            try:
                await websocket.close(code=1011)
            except Exception:
                pass
    finally:
        for task in (forward, client):
            task.cancel()
        await asyncio.gather(forward, client, return_exceptions=True)
        ws_manager.disconnect(user_id, websocket)
        try:
            await pubsub.unsubscribe(channel)
        finally:
            await pubsub.aclose()
            await r.aclose()


@router.get("/notifications/templates", response_model=list[NotificationTemplateResponse])
async def list_templates(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(NotificationTemplate).where(NotificationTemplate.is_active == True))
    return result.scalars().all()


@router.post(
    "/notifications/templates",
    response_model=NotificationTemplateResponse,
    status_code=201,
    dependencies=[Depends(require_admin)],
)
async def create_template(payload: NotificationTemplateCreate, db: AsyncSession = Depends(get_db)):
    import json as _json

    for source in (payload.subject_template, payload.body_template):
        if source:
            try:
                template_service.check_syntax(source)
            except ValueError as e:
                raise HTTPException(status_code=422, detail=str(e)) from e
    tmpl = NotificationTemplate(
        name=payload.name,
        channel=payload.channel,
        subject_template=payload.subject_template,
        body_template=payload.body_template,
        variables=_json.dumps(payload.variables) if payload.variables else "[]",
        is_active=True,
    )
    db.add(tmpl)
    await db.flush()
    return tmpl


@router.post("/notifications/device-tokens", response_model=DeviceTokenResponse, status_code=201)
async def register_device_token(
    payload: DeviceTokenCreate, db: AsyncSession = Depends(get_db), caller: Caller = Depends(require_caller)
):
    ensure_self_or_admin(payload.user_id, caller)
    result = await db.execute(select(DeviceToken).where(DeviceToken.token == payload.token))
    existing = result.scalar_one_or_none()
    if existing:
        # A device that signs in as someone else must stop receiving the previous user's pushes.
        existing.user_id = payload.user_id
        existing.is_active = True
        existing.platform = payload.platform
        await db.flush()
        return existing
    token = DeviceToken(user_id=payload.user_id, token=payload.token, platform=payload.platform)
    db.add(token)
    await db.flush()
    return token


@router.post("/notifications/device-tokens/unregister", status_code=204)
async def unregister_device_token(
    payload: DeviceTokenRemove, db: AsyncSession = Depends(get_db), caller: Caller = Depends(require_caller)
):
    """Signing out: this device stops getting the user's pushes. Unknown tokens are fine (204)."""
    existing = (await db.execute(select(DeviceToken).where(DeviceToken.token == payload.token))).scalar_one_or_none()
    if existing is not None and (caller.is_admin or existing.user_id == caller.user_id):
        existing.is_active = False
        await db.flush()
    return Response(status_code=204)
