from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import json
import structlog

from app.database import get_db
from app.schemas.notification import (
    NotificationCreate, NotificationResponse, NotificationListResponse,
    NotificationTemplateCreate, NotificationTemplateResponse,
    DeviceTokenCreate, DeviceTokenResponse,
)
from app.services.notification_service import notification_service
from app.models.notification import NotificationTemplate, DeviceToken, NotificationPreference
from app.core.exceptions import NotificationServiceError, TemplateNotFoundError, NotificationNotFoundError
from sqlalchemy import select
import redis.asyncio as aioredis
from app.config import settings

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


@router.post("/notifications/send", response_model=NotificationResponse, status_code=201)
async def send_notification(
    payload: NotificationCreate,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    try:
        notif = await notification_service.send(
            db, redis,
            payload.user_id,
            payload.template_name,
            payload.variables,
            payload.channels,
            payload.priority,
        )
        return notif
    except TemplateNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except NotificationServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/notifications/me", response_model=NotificationListResponse)
async def get_my_notifications(
    user_id: str = Query(...),
    unread_only: bool = Query(False),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await notification_service.get_notifications(db, user_id, unread_only, page, per_page)


@router.post("/notifications/{notification_id}/read")
async def mark_read(
    notification_id: str,
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    try:
        await notification_service.mark_as_read(db, notification_id, user_id)
        return {"success": True}
    except NotificationNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/notifications/read-all")
async def mark_all_read(
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    count = await notification_service.mark_all_read(db, user_id)
    return {"marked_read": count}


@router.get("/notifications/count/unread")
async def unread_count(
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    count = await notification_service.get_unread_count(db, user_id)
    return {"unread_count": count}


@router.websocket("/ws/notifications/{user_id}")
async def ws_notifications(websocket: WebSocket, user_id: str):
    await ws_manager.connect(user_id, websocket)
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe(f"notifications:{user_id}")
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    await websocket.send_json(data)
                except Exception:
                    pass
    except WebSocketDisconnect:
        ws_manager.disconnect(user_id, websocket)
    finally:
        await pubsub.unsubscribe(f"notifications:{user_id}")
        await r.aclose()


@router.get("/notifications/templates", response_model=list[NotificationTemplateResponse])
async def list_templates(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(NotificationTemplate).where(NotificationTemplate.is_active == True))
    return result.scalars().all()


@router.post("/notifications/templates", response_model=NotificationTemplateResponse, status_code=201)
async def create_template(payload: NotificationTemplateCreate, db: AsyncSession = Depends(get_db)):
    import json as _json
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
async def register_device_token(payload: DeviceTokenCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(DeviceToken).where(DeviceToken.token == payload.token)
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.is_active = True
        existing.platform = payload.platform
        await db.flush()
        return existing
    token = DeviceToken(user_id=payload.user_id, token=payload.token, platform=payload.platform)
    db.add(token)
    await db.flush()
    return token
