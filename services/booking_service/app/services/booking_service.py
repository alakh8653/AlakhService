import uuid
import random
from datetime import datetime, timezone
from typing import List, Optional
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from app.models.booking import Booking, BookingStatusHistory, BookingAssignment
from app.schemas.booking import BookingCreate, BookingStatusUpdate
from app.core.fsm import booking_fsm, BookingStatus

log = structlog.get_logger()


class BookingService:

    async def _generate_booking_number(self, db: AsyncSession) -> str:
        """Generate a unique booking number with collision detection."""
        from sqlalchemy import select as sa_select
        for _ in range(10):
            number = "BK" + str(random.randint(10000000, 99999999))
            result = await db.execute(sa_select(Booking.id).where(Booking.booking_number == number))
            if result.scalar_one_or_none() is None:
                return number
        # Fallback to UUID-based number to guarantee uniqueness
        return "BK" + uuid.uuid4().hex[:8].upper()

    async def create_booking(self, db: AsyncSession, customer_id: str, booking_data: BookingCreate) -> Booking:
        now = datetime.now(timezone.utc)
        booking = Booking(
            id=str(uuid.uuid4()),
            booking_number=await self._generate_booking_number(db),
            customer_id=customer_id,
            service_id=booking_data.service_id,
            status=BookingStatus.PENDING.value,
            scheduled_at=booking_data.scheduled_at,
            duration_minutes=booking_data.duration_minutes,
            address_id=booking_data.address_id,
            notes=booking_data.notes,
            total_amount=booking_data.total_amount,
            created_at=now,
            updated_at=now,
        )
        db.add(booking)
        await db.flush()

        history = BookingStatusHistory(
            id=str(uuid.uuid4()),
            booking_id=booking.id,
            from_status=None,
            to_status=BookingStatus.PENDING.value,
            changed_by=customer_id,
            reason="Booking created",
            created_at=now,
        )
        db.add(history)
        await db.flush()

        log.info("booking_created", booking_id=booking.id, customer_id=customer_id)
        return booking

    async def get_booking(self, db: AsyncSession, booking_id: str, user_id: Optional[str] = None) -> Optional[Booking]:
        result = await db.execute(select(Booking).where(Booking.id == booking_id))
        return result.scalar_one_or_none()

    async def list_bookings(
        self,
        db: AsyncSession,
        user_id: str,
        page: int = 1,
        per_page: int = 20,
        status_filter: Optional[str] = None,
    ) -> dict:
        query = select(Booking).where(Booking.customer_id == user_id)
        if status_filter:
            query = query.where(Booking.status == status_filter)

        count_result = await db.execute(select(func.count()).select_from(query.subquery()))
        total = count_result.scalar() or 0

        query = query.offset((page - 1) * per_page).limit(per_page).order_by(Booking.created_at.desc())
        result = await db.execute(query)
        items = list(result.scalars().all())

        return {
            "items": items,
            "total": total,
            "page": page,
            "per_page": per_page,
        }

    async def transition_status(
        self,
        db: AsyncSession,
        booking_id: str,
        new_status: str,
        user_id: str,
        reason: Optional[str] = None,
    ) -> Booking:
        result = await db.execute(select(Booking).where(Booking.id == booking_id))
        booking = result.scalar_one_or_none()
        if not booking:
            raise ValueError(f"Booking {booking_id} not found")

        from_status = BookingStatus(booking.status)
        to_status = BookingStatus(new_status)

        booking_fsm.transition(from_status, to_status)

        old_status = booking.status
        booking.status = to_status.value
        booking.updated_at = datetime.now(timezone.utc)

        history = BookingStatusHistory(
            id=str(uuid.uuid4()),
            booking_id=booking.id,
            from_status=old_status,
            to_status=to_status.value,
            changed_by=user_id,
            reason=reason,
            created_at=datetime.now(timezone.utc),
        )
        db.add(history)
        await db.flush()

        log.info("booking_status_changed", booking_id=booking.id, from_status=old_status, to_status=new_status)
        return booking

    async def assign_provider(self, db: AsyncSession, booking_id: str, provider_id: str) -> Booking:
        booking = await self.transition_status(
            db, booking_id, BookingStatus.ASSIGNED.value, provider_id, "Provider assigned"
        )

        assignment = BookingAssignment(
            id=str(uuid.uuid4()),
            booking_id=booking_id,
            provider_id=provider_id,
            assigned_at=datetime.now(timezone.utc),
        )
        db.add(assignment)
        booking.provider_id = provider_id
        await db.flush()
        return booking

    async def cancel_booking(self, db: AsyncSession, booking_id: str, user_id: str, reason: str) -> Booking:
        booking = await self.transition_status(
            db, booking_id, BookingStatus.CANCELLED.value, user_id, reason
        )
        booking.cancellation_reason = reason
        await db.flush()
        return booking

    async def complete_booking(self, db: AsyncSession, booking_id: str, user_id: str) -> Booking:
        return await self.transition_status(
            db, booking_id, BookingStatus.COMPLETED.value, user_id, "Service completed"
        )

    async def get_booking_history(self, db: AsyncSession, booking_id: str) -> List[BookingStatusHistory]:
        result = await db.execute(
            select(BookingStatusHistory)
            .where(BookingStatusHistory.booking_id == booking_id)
            .order_by(BookingStatusHistory.created_at.asc())
        )
        return list(result.scalars().all())


booking_service = BookingService()
