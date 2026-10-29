"""The booking worker: reminders, expiring unconfirmed bookings, retrying payment messages, and asking
customers some weeks after a visit whether they want to book it again.

It runs as an asyncio task inside every booking_service replica (REMINDERS_ENABLED). Replicas never
do the same work twice: candidate rows are taken with SELECT ... FOR UPDATE SKIP LOCKED, and each
reminder has its own "sent" column set in the same transaction, so a booking another replica is
handling is skipped and a reminder already sent is never selected again.

Notifications are sent after the transaction commits; one that cannot be delivered is logged and not
retried (a missed reminder is better than two).
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable, List, Optional, Tuple

import structlog
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core import availability, live_queue, payments, waitlist
from app.core.fsm import BookingStatus
from app.core.notifier import Notifier, notify_booking, snapshot
from app.models.booking import Booking
from app.services.booking_service import booking_service

log = structlog.get_logger()

SYSTEM = "system"
EXPIRED_REASON = "Shop did not confirm"
# Bookings that will happen: confirmed, perhaps with a provider assigned, not started yet.
REMINDER_STATUSES = (BookingStatus.CONFIRMED.value, BookingStatus.ASSIGNED.value)

OwnerLookup = Callable[[str], Awaitable[Optional[str]]]


def _skip_locked(query, db: AsyncSession):
    if db.get_bind().dialect.name == "postgresql":
        return query.with_for_update(skip_locked=True)
    return query


async def due_reminders(db: AsyncSession, now: datetime, limit: int = 200) -> List[Tuple[Booking, str]]:
    """Takes the bookings owed a reminder and marks them sent; returns (booking, "24h" or "1h").

    The 24-hour reminder goes out a day ahead, unless the booking is less than an hour away by then
    (made at the last minute), when only the one-hour reminder is sent.
    """
    hour, day = now + timedelta(hours=1), now + timedelta(hours=24)
    query = _skip_locked(
        select(Booking)
        .where(
            Booking.status.in_(REMINDER_STATUSES),
            Booking.scheduled_at > now,
            or_(
                and_(Booking.reminder_1h_sent_at.is_(None), Booking.scheduled_at <= hour),
                and_(Booking.reminder_24h_sent_at.is_(None), Booking.scheduled_at <= day),
            ),
        )
        .order_by(Booking.scheduled_at)
        .limit(limit),
        db,
    )
    out = []
    for booking in (await db.execute(query)).scalars().all():
        at = booking.scheduled_at if booking.scheduled_at.tzinfo else booking.scheduled_at.replace(tzinfo=timezone.utc)
        if at <= hour:
            if booking.reminder_1h_sent_at is not None:
                continue
            booking.reminder_1h_sent_at = now
            booking.reminder_24h_sent_at = booking.reminder_24h_sent_at or now  # never a "tomorrow" after this
            out.append((booking, "1h"))
        else:
            booking.reminder_24h_sent_at = now
            out.append((booking, "24h"))
    await db.flush()
    return out


async def due_rebook_reminders(db: AsyncSession, now: datetime, limit: int = 200) -> List[Booking]:
    """Completed visits REBOOK_REMINDER_DAYS old whose customer has not booked that service again since;
    marks each asked, so it is asked once."""
    days = settings.REBOOK_REMINDER_DAYS
    if days <= 0:
        return []
    newest, oldest = now - timedelta(days=days), now - timedelta(days=days + settings.REBOOK_REMINDER_WINDOW_DAYS)
    query = _skip_locked(
        select(Booking)
        .where(
            Booking.status == BookingStatus.COMPLETED.value,
            Booking.rebook_reminder_sent_at.is_(None),
            Booking.scheduled_at <= newest,
            Booking.scheduled_at > oldest,
        )
        .order_by(Booking.scheduled_at)
        .limit(limit),
        db,
    )
    due = []
    for visit in (await db.execute(query)).scalars().all():
        visit.rebook_reminder_sent_at = now
        later = await db.execute(
            select(Booking.id)
            .where(
                Booking.customer_id == visit.customer_id,
                Booking.service_id == visit.service_id,
                Booking.id != visit.id,
                Booking.scheduled_at > visit.scheduled_at,
                Booking.status != BookingStatus.CANCELLED.value,
            )
            .limit(1)
        )
        if later.first() is None:  # already booked again: marked, not asked
            due.append(visit)
    await db.flush()
    return due


async def due_queue_notices(db: AsyncSession, now: datetime, lookup_schedule) -> List[Tuple[Booking, str, dict]]:
    """Today's visits at the shop whose customer should hear that their turn is near ("turn_soon") or that
    the shop is running late ("running_late"); each is marked so it is sent once. Returns (booking, kind, data)."""
    if settings.TURN_SOON_MINUTES <= 0 and settings.RUNNING_LATE_MINUTES <= 0:
        return []
    window = (now - timedelta(hours=12), now + timedelta(hours=14))  # covers "today" in any shop's zone
    rows = (
        (
            await db.execute(
                select(Booking.shop_id)
                .where(
                    Booking.status.in_(live_queue.WAITING),
                    Booking.service_mode == live_queue.AT_SHOP,
                    Booking.scheduled_at >= window[0],
                    Booking.scheduled_at < window[1],
                    or_(Booking.turn_soon_sent_at.is_(None), Booking.running_late_sent_at.is_(None)),
                )
                .distinct()
            )
        )
        .scalars()
        .all()
    )
    out: List[Tuple[Booking, str, dict]] = []
    for shop_id in [s for s in rows if s]:
        try:
            schedule = availability.Schedule.from_shop_service(await lookup_schedule(shop_id))
        except Exception as e:  # shop_service down: try again next pass
            log.warning("queue_notice_schedule_failed", shop_id=shop_id, error=str(e))
            continue
        spots = await live_queue.shop_queue(db, shop_id, schedule, now)
        waiting = [s for s in spots.values() if s.state in (live_queue.WAITING_STATE, live_queue.YOUR_TURN)]
        if not waiting:
            continue
        for b in await booking_service_get(db, [s.booking_id for s in waiting]):
            spot = spots[b.id]
            data = {
                "wait_minutes": spot.wait_minutes,
                "late_minutes": spot.running_late_minutes,
                "position": spot.position,
            }
            if (
                settings.TURN_SOON_MINUTES > 0
                and b.turn_soon_sent_at is None
                and spot.wait_minutes <= settings.TURN_SOON_MINUTES
            ):
                b.turn_soon_sent_at = now
                # Nearly their turn: a later "running late" would only confuse.
                b.running_late_sent_at = b.running_late_sent_at or now
                out.append((b, "turn_soon", data))
            elif (
                settings.RUNNING_LATE_MINUTES > 0
                and b.running_late_sent_at is None
                and spot.running_late_minutes >= settings.RUNNING_LATE_MINUTES
            ):
                b.running_late_sent_at = now
                out.append((b, "running_late", data))
    await db.flush()
    return out


async def booking_service_get(db: AsyncSession, ids: List[str]) -> List[Booking]:
    return await booking_service.get_bookings(db, ids)


async def expire_unconfirmed(
    db: AsyncSession, now: datetime, after_hours: float, limit: int = 100
) -> List[Tuple[Booking, str]]:
    """Cancels PENDING bookings the shop has not confirmed in [after_hours], or by their start time.

    Each is queued for a full refund (the shop's doing). Returns (booking, payment outbox id).
    """
    query = _skip_locked(
        select(Booking)
        .where(
            Booking.status == BookingStatus.PENDING.value,
            or_(Booking.created_at <= now - timedelta(hours=after_hours), Booking.scheduled_at <= now),
        )
        .order_by(Booking.created_at)
        .limit(limit),
        db,
    )
    out = []
    for booking in (await db.execute(query)).scalars().all():
        booking = await booking_service.cancel_booking(db, booking.id, SYSTEM, EXPIRED_REASON)
        queued = await payments.enqueue(db, booking, payments.CANCELLED, "shop")
        out.append((booking, queued.id))
        log.info("booking_expired", booking_id=booking.id)
    return out


async def run_once(
    factory,
    notifier: Notifier,
    lookup_owner: OwnerLookup,
    client: payments.PaymentClient,
    now: Optional[datetime] = None,
    lookup_schedule=None,
) -> dict:
    """One pass of the worker; returns what it did."""
    now = now or datetime.now(timezone.utc)
    async with factory() as db:
        reminders = [(snapshot(b), label) for b, label in await due_reminders(db, now)]
        await db.commit()
    async with factory() as db:
        rebook = [snapshot(b) for b in await due_rebook_reminders(db, now)]
        await db.commit()
    queue_notices = []
    if lookup_schedule is not None:
        async with factory() as db:
            queue_notices = [
                (snapshot(b), kind, data) for b, kind, data in await due_queue_notices(db, now, lookup_schedule)
            ]
            await db.commit()
    async with factory() as db:
        expired_rows = await expire_unconfirmed(db, now, settings.EXPIRE_PENDING_AFTER_HOURS)
        expired = [(snapshot(b), outbox_id) for b, outbox_id in expired_rows]
        # An expired request frees its time for anyone waiting for that day.
        waiting = []
        for b, _ in expired_rows:
            waiting += await waitlist.time_opened(db, b.shop_id, b.scheduled_at, except_customer=b.customer_id)
        await db.commit()
    for _snap, outbox_id in expired:
        await payments.deliver_now(factory, client, outbox_id)
    async with factory() as db:
        retried = await payments.deliver_due(db, client, now)
        await db.commit()

    for snap, label in reminders:
        await notify_booking(notifier, snap, "booking.reminder", None, lookup_owner, extra={"reminder": label})
    await waitlist.tell(notifier, waiting)
    for snap, kind, data in queue_notices:
        await notify_booking(notifier, snap, f"booking.{kind}", None, lookup_owner, roles=("customer",), extra=data)
    for snap in rebook:
        await notify_booking(notifier, snap, "booking.rebook", None, lookup_owner, roles=("customer",))
    for snap, _ in expired:
        await notify_booking(
            notifier,
            snap,
            "booking.expired",
            None,
            lookup_owner,
            roles=("customer", "shop"),
            extra={"reason": EXPIRED_REASON},
        )
    summary = {
        "reminders": len(reminders),
        "rebook_reminders": len(rebook),
        "queue_notices": len(queue_notices),
        "expired": len(expired),
        "payment_retries": len(retried),
    }
    if any(summary.values()):
        log.info("booking_worker_pass", **summary)
    return summary


async def run_forever(
    factory, notifier: Notifier, lookup_owner: OwnerLookup, client: payments.PaymentClient, lookup_schedule=None
) -> None:
    log.info("booking_worker_started", interval=settings.WORKER_INTERVAL_SECONDS)
    while True:
        try:
            await run_once(factory, notifier, lookup_owner, client, lookup_schedule=lookup_schedule)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # a bad pass never stops the next one
            log.error("booking_worker_failed", error=str(e))
        await asyncio.sleep(settings.WORKER_INTERVAL_SECONDS)
