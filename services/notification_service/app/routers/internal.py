from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.internal import require_internal
from app.database import get_db
from app.routers.notifications import get_redis
from app.services.notification_service import notification_service

router = APIRouter(dependencies=[Depends(require_internal)])


class Recipient(BaseModel):
    user_id: str
    # customer, provider or shop: picks the wording (e.g. "New job" vs "Provider assigned").
    role: Optional[str] = None


class EventNotification(BaseModel):
    event: str = Field(examples=["booking.confirmed"])
    recipients: List[Recipient] = Field(min_length=1, max_length=20)
    data: Dict[str, Any] = {}


@router.post("/internal/notifications/events")
async def notify_event(
    body: EventNotification,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    """Tells each recipient about a booking or payment event (other platform services only).

    Recorded and pushed straight away; SMS and email for people without the app go after the response.
    """
    created = 0
    for r in body.recipients:
        notif = await notification_service.notify_event(db, redis, r.user_id, body.event, r.role, body.data)
        if notif:
            created += 1
            background.add_task(
                notification_service.deliver_fallback,
                r.user_id,
                body.event,
                r.role,
                notif.title,
                notif.body,
                body.data,
                notif.channel == "push",
            )
    return {"created": created}
