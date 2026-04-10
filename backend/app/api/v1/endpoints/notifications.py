from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_active_user
from app.models.user import User
from app.schemas.notification import DeviceTokenRegister, NotificationRead
from app.services.notification_service import (
    delete_notification,
    get_user_notifications,
    mark_all_as_read,
    mark_as_read,
)
from app.api.v1.dependencies import pagination_params

router = APIRouter()


@router.get("/", response_model=list[NotificationRead])
async def list_notifications(
    pagination: dict = Depends(pagination_params),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """List all notifications for the current user."""
    return await get_user_notifications(
        db, user_id=current_user.id, skip=pagination["skip"], limit=pagination["limit"]
    )


@router.put("/{notification_id}/read", response_model=NotificationRead)
async def read_notification(
    notification_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark a single notification as read."""
    return await mark_as_read(db, notification_id=notification_id, user_id=current_user.id)


@router.post("/mark-all-read")
async def read_all_notifications(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark all notifications for the current user as read."""
    await mark_all_as_read(db, user_id=current_user.id)
    return {"message": "All notifications marked as read"}


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_notification(
    notification_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a specific notification."""
    await delete_notification(db, notification_id=notification_id, user_id=current_user.id)


@router.post("/subscribe")
async def subscribe_push(
    device_token: DeviceTokenRegister,
    current_user: User = Depends(get_current_active_user),
):
    """Register a device token for push notifications."""
    # TODO: persist device_token to user's profile and subscribe via FCM
    return {"message": "Device token registered", "platform": device_token.platform}
