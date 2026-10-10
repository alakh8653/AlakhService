import random
import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import List, Optional

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.fsm import BookingStatus, booking_fsm
from app.models.booking import Booking, BookingAssignment, BookingStatusHistory
from app.schemas.booking import BookingCreate

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
            shop_id=booking_data.shop_id,
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
        """Bookings the provider is currently working on (assigned, on the way, or in progress)."""
        result = await db.execute(
            select(Booking).where(
                Booking.provider_id == provider_id,
                Booking.status.in_(
                    [
                        BookingStatus.ASSIGNED.value,
                        BookingStatus.PROVIDER_EN_ROUTE.value,
                        BookingStatus.IN_PROGRESS.value,
                    ]
                ),
            )
        )
        return list(result.scalars().all())

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

    async def shop_summary(self, db: AsyncSession, shop_id: str, date_from: date, date_to: date, top_n: int = 5) -> dict:
        """Totals for bookings scheduled in the range; revenue counts completed bookings only."""
        bookings = (await db.execute(self._shop_query(shop_id, date_from=date_from, date_to=date_to))).scalars().all()

        by_status: dict = {}
        by_day = {date_from + timedelta(days=i): {"revenue": 0, "bookings": 0} for i in range((date_to - date_from).days + 1)}
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
        # Set explicitly so the column's server-side onupdate does not expire it after the flush.
        booking.updated_at = datetime.now(timezone.utc)
        await db.flush()
        return booking

    async def cancel_booking(self, db: AsyncSession, booking_id: str, user_id: str, reason: str) -> Booking:
        booking = await self.transition_status(
            db, booking_id, BookingStatus.CANCELLED.value, user_id, reason
        )
        booking.cancellation_reason = reason
        # Set explicitly so the column's server-side onupdate does not expire it after the flush.
        booking.updated_at = datetime.now(timezone.utc)
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
