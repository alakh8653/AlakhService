import random
import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import List, Optional

import structlog
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.fsm import PICKUP_DROP, BookingStatus, booking_fsm, mode_problem
from app.models.booking import Booking, BookingAssignment, BookingStatusHistory
from app.schemas.booking import BookingCreate

log = structlog.get_logger()

# A provider with a booking in one of these is busy for its scheduled time.
ACTIVE_STATUSES = [
    BookingStatus.ASSIGNED.value,
    BookingStatus.PROVIDER_EN_ROUTE.value,
    BookingStatus.PICKED_UP.value,
    BookingStatus.IN_PROGRESS.value,
    BookingStatus.OUT_FOR_DELIVERY.value,
]


class ProviderUnavailable(Exception):
    """The provider already has an active job at the booking's time."""


def _utc(at: datetime) -> datetime:
    # SQLite hands back naive datetimes; they are stored as UTC.
    return at if at.tzinfo else at.replace(tzinfo=timezone.utc)


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

    async def create_booking(
        self,
        db: AsyncSession,
        customer_id: str,
        booking_data: BookingCreate,
        metadata_json: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        request_hash: Optional[str] = None,
    ) -> Booking:
        now = datetime.now(timezone.utc)
        booking = Booking(
            id=str(uuid.uuid4()),
            booking_number=await self._generate_booking_number(db),
            customer_id=customer_id,
            service_id=booking_data.service_id,
            shop_id=booking_data.shop_id,
            status=BookingStatus.PENDING.value,
            scheduled_at=booking_data.scheduled_at,
            duration_minutes=booking_data.duration_minutes,
            address_id=booking_data.address_id,
            service_mode=booking_data.service_mode,
            item_description=booking_data.item_description,
            notes=booking_data.notes,
            total_amount=booking_data.total_amount,
            metadata_json=metadata_json,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
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

    async def hold_idempotency_key(self, db: AsyncSession, customer_id: str, key: str) -> None:
        """Makes requests with the same key wait for each other, until this transaction ends.

        Without it two copies of a request could both price the booking and use up its coupon before the
        unique constraint stops the second insert. Only PostgreSQL has the lock; the constraint holds anywhere.
        """
        if db.get_bind().dialect.name == "postgresql":
            await db.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"), {"k": f"booking:{customer_id}:{key}"}
            )

    async def get_by_idempotency_key(self, db: AsyncSession, customer_id: str, key: str) -> Optional[Booking]:
        result = await db.execute(
            select(Booking).where(Booking.customer_id == customer_id, Booking.idempotency_key == key)
        )
        return result.scalar_one_or_none()

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
        as_provider: bool = False,
    ) -> dict:
        """The customer's own bookings, or with [as_provider] the jobs assigned to them."""
        owner_column = Booking.provider_id if as_provider else Booking.customer_id
        query = select(Booking).where(owner_column == user_id)
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

    def _shop_query(
        self,
        shop_id: str,
        status_filter: Optional[str] = None,
        provider_id: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ):
        """Bookings of one shop, optionally narrowed by status, assignee and scheduled date (inclusive)."""
        query = select(Booking).where(Booking.shop_id == shop_id)
        if status_filter:
            query = query.where(Booking.status == status_filter)
        if provider_id:
            query = query.where(Booking.provider_id == provider_id)
        if date_from:
            query = query.where(Booking.scheduled_at >= datetime.combine(date_from, time.min, tzinfo=timezone.utc))
        if date_to:
            query = query.where(
                Booking.scheduled_at < datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
            )
        return query

    async def active_bookings_with_provider(self, db: AsyncSession, provider_id: str) -> List[Booking]:
        """Bookings the provider is currently working on (assigned, on the way, holding the
        customer's item, in progress, or bringing it back)."""
        result = await db.execute(
            select(Booking).where(Booking.provider_id == provider_id, Booking.status.in_(ACTIVE_STATUSES))
        )
        return list(result.scalars().all())

    async def overlapping_job(self, db: AsyncSession, booking: Booking, provider_id: str) -> Optional[Booking]:
        """One of the provider's active jobs whose time overlaps [booking]'s, if any."""
        start = _utc(booking.scheduled_at)
        end = start + timedelta(minutes=booking.duration_minutes)
        # Compared in Python: interval arithmetic on columns differs between SQLite and PostgreSQL.
        for other in await self.active_bookings_with_provider(db, provider_id):
            other_start = _utc(other.scheduled_at)
            other_end = other_start + timedelta(minutes=other.duration_minutes)
            if other.id != booking.id and other_start < end and start < other_end:
                return other
        return None

    async def list_shop_bookings(
        self,
        db: AsyncSession,
        shop_id: str,
        page: int = 1,
        per_page: int = 20,
        status_filter: Optional[str] = None,
        provider_id: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> dict:
        query = self._shop_query(shop_id, status_filter, provider_id, date_from, date_to)
        total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
        result = await db.execute(
            query.order_by(Booking.scheduled_at.desc(), Booking.id).offset((page - 1) * per_page).limit(per_page)
        )
        return {"items": list(result.scalars().all()), "total": total, "page": page, "per_page": per_page}

    async def shop_summary(
        self, db: AsyncSession, shop_id: str, date_from: date, date_to: date, top_n: int = 5
    ) -> dict:
        """Totals for bookings scheduled in the range; revenue counts completed bookings only."""
        bookings = (await db.execute(self._shop_query(shop_id, date_from=date_from, date_to=date_to))).scalars().all()

        by_status: dict = {}
        by_day = {
            date_from + timedelta(days=i): {"revenue": 0, "bookings": 0} for i in range((date_to - date_from).days + 1)
        }
        by_service: dict = {}
        for b in bookings:
            by_status[b.status] = by_status.get(b.status, 0) + 1
            day = b.scheduled_at.astimezone(timezone.utc).date() if b.scheduled_at.tzinfo else b.scheduled_at.date()
            revenue = b.total_amount if b.status == BookingStatus.COMPLETED.value else 0
            if day in by_day:
                by_day[day]["bookings"] += 1
                by_day[day]["revenue"] += revenue
            svc = by_service.setdefault(b.service_id, {"service_id": b.service_id, "bookings": 0, "revenue": 0})
            svc["bookings"] += 1
            svc["revenue"] += revenue

        return {
            "shop_id": shop_id,
            "date_from": date_from,
            "date_to": date_to,
            "total_bookings": len(bookings),
            "total_revenue": sum(d["revenue"] for d in by_day.values()),
            "unique_customers": len({b.customer_id for b in bookings}),
            "by_status": by_status,
            "by_day": [{"day": d, **v} for d, v in sorted(by_day.items())],
            "top_services": sorted(by_service.values(), key=lambda s: (-s["bookings"], -s["revenue"]))[:top_n],
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

        # The delivery mode's reason first: it says what to do instead ("pick up the item first").
        problem = mode_problem(booking.service_mode, from_status, to_status)
        if problem:
            raise ValueError(problem)
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

    async def assign_provider(
        self, db: AsyncSession, booking_id: str, provider_id: str, assigned_by: Optional[str] = None
    ) -> Booking:
        booking = await self.get_booking(db, booking_id)
        # Only when the booking could be assigned at all, so an invalid transition still says why.
        if booking and booking_fsm.can_transition(BookingStatus(booking.status), BookingStatus.ASSIGNED):
            clash = await self.overlapping_job(db, booking, provider_id)
            if clash:
                raise ProviderUnavailable(
                    f"Provider is busy with booking {clash.booking_number} "
                    f"({_utc(clash.scheduled_at):%Y-%m-%d %H:%M} UTC, {clash.duration_minutes} min), "
                    "which overlaps this one"
                )
        booking = await self.transition_status(
            db, booking_id, BookingStatus.ASSIGNED.value, assigned_by or provider_id, "Provider assigned"
        )

        assignment = BookingAssignment(
            id=str(uuid.uuid4()),
            booking_id=booking_id,
            provider_id=provider_id,
            assigned_at=datetime.now(timezone.utc),
        )
        db.add(assignment)
        booking.provider_id = provider_id
        # Set explicitly so the column's server-side onupdate does not expire it after the flush.
        booking.updated_at = datetime.now(timezone.utc)
        await db.flush()
        return booking

    # A return time can be promised until the item is on its way back.
    READY_BY_STATUSES = {
        BookingStatus.PENDING.value,
        BookingStatus.CONFIRMED.value,
        BookingStatus.ASSIGNED.value,
        BookingStatus.PROVIDER_EN_ROUTE.value,
        BookingStatus.PICKED_UP.value,
        BookingStatus.IN_PROGRESS.value,
    }

    async def set_ready_by(self, db: AsyncSession, booking: Booking, ready_by: Optional[datetime]) -> Booking:
        """Sets (or with None clears) when a pickup & drop item should be back with the customer."""
        if booking.service_mode != PICKUP_DROP:
            raise ValueError("A return time applies only to pickup & drop bookings")
        if booking.status not in self.READY_BY_STATUSES:
            raise ValueError("The return time can no longer be changed for this booking")
        if ready_by is not None:
            ready_by = ready_by if ready_by.tzinfo else ready_by.replace(tzinfo=timezone.utc)
            scheduled = booking.scheduled_at
            scheduled = scheduled if scheduled.tzinfo else scheduled.replace(tzinfo=timezone.utc)
            if ready_by <= max(scheduled, datetime.now(timezone.utc)):
                raise ValueError("The return time must be after the pickup and in the future")
        booking.ready_by = ready_by
        # Set explicitly so the column's server-side onupdate does not expire it after the flush.
        booking.updated_at = datetime.now(timezone.utc)
        await db.flush()
        return booking

    async def cancel_booking(self, db: AsyncSession, booking_id: str, user_id: str, reason: str) -> Booking:
        booking = await self.transition_status(db, booking_id, BookingStatus.CANCELLED.value, user_id, reason)
        booking.cancellation_reason = reason
        # Set explicitly so the column's server-side onupdate does not expire it after the flush.
        booking.updated_at = datetime.now(timezone.utc)
        await db.flush()
        return booking

    async def complete_booking(self, db: AsyncSession, booking_id: str, user_id: str) -> Booking:
        return await self.transition_status(db, booking_id, BookingStatus.COMPLETED.value, user_id, "Service completed")

    async def get_booking_history(self, db: AsyncSession, booking_id: str) -> List[BookingStatusHistory]:
        result = await db.execute(
            select(BookingStatusHistory)
            .where(BookingStatusHistory.booking_id == booking_id)
            .order_by(BookingStatusHistory.created_at.asc())
        )
        return list(result.scalars().all())


booking_service = BookingService()
