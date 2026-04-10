import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.models.notification import Notification


async def create_notification(
    db: AsyncSession,
    user_id: uuid.UUID,
    title: str,
    body: str,
    notification_type: str,
    data: Any = None,
) -> Notification:
    notification = Notification(
        user_id=user_id,
        title=title,
        body=body,
        notification_type=notification_type,
        data=data,
    )
    db.add(notification)
    await db.flush()
    await db.refresh(notification)
    return notification


async def get_user_notifications(
    db: AsyncSession, user_id: uuid.UUID, skip: int = 0, limit: int = 20
) -> list[Notification]:
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


async def mark_as_read(
    db: AsyncSession, notification_id: uuid.UUID, user_id: uuid.UUID
) -> Notification:
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id, Notification.user_id == user_id
        )
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise NotFoundException(resource_name="Notification")
    notification.is_read = True
    await db.flush()
    await db.refresh(notification)
    return notification


async def mark_all_as_read(db: AsyncSession, user_id: uuid.UUID) -> None:
    await db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read == False)  # noqa: E712
        .values(is_read=True)
    )
    await db.flush()


async def send_push_notification(
    device_token: str, title: str, body: str, data: Any = None
) -> None:
    """Placeholder for Firebase Cloud Messaging (FCM) push notification."""
    # TODO: integrate with firebase-admin SDK
    # messaging.send(messaging.Message(notification=..., token=device_token))
    pass


async def delete_notification(
    db: AsyncSession, notification_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id, Notification.user_id == user_id
        )
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise NotFoundException(resource_name="Notification")
    await db.delete(notification)
    await db.flush()
