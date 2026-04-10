import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BookingException, NotFoundException, PermissionDeniedException
from app.models.booking import Booking
from app.schemas.booking import BookingCreate, BookingUpdate
from app.services.service_service import get_service


async def create_booking(
    db: AsyncSession,
    user_id: uuid.UUID,
    booking_create: BookingCreate,
) -> Booking:
    service = await get_service(db, booking_create.service_id)
    booking = Booking(
        user_id=user_id,
        service_id=booking_create.service_id,
        scheduled_at=booking_create.scheduled_at,
        notes=booking_create.notes,
        total_amount=service.price,
        status="PENDING",
    )
    db.add(booking)
    await db.flush()
    await db.refresh(booking)
    return booking


async def get_booking(db: AsyncSession, booking_id: uuid.UUID) -> Booking:
    result = await db.execute(
        select(Booking)
        .where(Booking.id == booking_id)
        .options(selectinload(Booking.service))
    )
    booking = result.scalar_one_or_none()
    if not booking:
        raise NotFoundException(resource_name="Booking")
    return booking


async def get_user_bookings(
    db: AsyncSession, user_id: uuid.UUID, skip: int = 0, limit: int = 20
) -> list[Booking]:
    result = await db.execute(
        select(Booking)
        .where(Booking.user_id == user_id)
        .options(selectinload(Booking.service))
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


async def update_booking(
    db: AsyncSession, booking_id: uuid.UUID, booking_update: BookingUpdate
) -> Booking:
    booking = await get_booking(db, booking_id)
    update_data = booking_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(booking, field, value)
    await db.flush()
    await db.refresh(booking)
    return booking


async def cancel_booking(
    db: AsyncSession, booking_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    booking = await get_booking(db, booking_id)
    if booking.user_id != user_id:
        raise PermissionDeniedException()
    if booking.status in ("COMPLETED", "CANCELLED"):
        raise BookingException()
    booking.status = "CANCELLED"
    await db.flush()


async def confirm_booking(db: AsyncSession, booking_id: uuid.UUID) -> Booking:
    booking = await get_booking(db, booking_id)
    if booking.status != "PENDING":
        raise BookingException()
    booking.status = "CONFIRMED"
    await db.flush()
    await db.refresh(booking)
    return booking
