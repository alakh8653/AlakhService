from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
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
async def notify_event(body: EventNotification, db: AsyncSession = Depends(get_db), redis=Depends(get_redis)):
    """Tells each recipient about a booking or payment event (other platform services only)."""
    created = 0
    for r in body.recipients:
        if await notification_service.notify_event(db, redis, r.user_id, body.event, r.role, body.data):
            created += 1
    return {"created": created}
