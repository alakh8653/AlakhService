"""The live queue at a shop today: each customer's place in line, how long until their turn, how late it runs.

Many customers can book the same time at a shop that serves several at once (its capacity). On the day,
a shop runs behind when services overrun or start late, so the booked time alone does not tell a customer
when they will be seen. The queue works it out from what is happening now:

- the shop has [capacity] places (chairs). A customer being served (IN_PROGRESS) holds one until their
  start plus the service's length, and never less than a minute from now while they are still in it;
- everyone else waiting today, at the shop, goes in booking order (booked time, then who booked first):
  each starts at the earliest of: a place coming free, their booked time, and now;
- their wait is that start minus now, and how late the shop runs is that start minus their booked time.

It is an estimate: the shop may take someone early or late. It is recomputed on every look.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.availability import Schedule
from app.core.fsm import AT_SHOP, BookingStatus
from app.models.booking import Booking, BookingStatusHistory

# Still to be seen today: requested, confirmed, or given to a provider, and not started.
WAITING = (BookingStatus.PENDING.value, BookingStatus.CONFIRMED.value, BookingStatus.ASSIGNED.value)
SERVING = BookingStatus.IN_PROGRESS.value
# Within this of their estimated start, a waiting customer is told it is their turn.
YOUR_TURN_WITHIN = timedelta(minutes=2)

WAITING_STATE, YOUR_TURN, IN_PROGRESS, NOT_TODAY, NOT_QUEUED = (
    "WAITING",
    "YOUR_TURN",
    "IN_PROGRESS",
    "NOT_TODAY",
    "NOT_QUEUED",
)


def _utc(at: datetime) -> datetime:
    return at.astimezone(timezone.utc) if at.tzinfo else at.replace(tzinfo=timezone.utc)


@dataclass
class QueueSpot:
    booking_id: str
    state: str
    # 1 for the first customer waiting; None while being served.
    position: Optional[int]
    people_ahead: int
    being_served: int
    estimated_start: datetime
    estimated_end: datetime
    wait_minutes: int
    running_late_minutes: int


@dataclass
class _Visit:
    id: str
    status: str
    scheduled_at: datetime
    duration: timedelta
    created_at: datetime
    started_at: Optional[datetime] = None


def compute(visits: List[_Visit], capacity: int, now: datetime) -> Dict[str, QueueSpot]:
    """The queue for one shop's day (see the module docstring). Pure, so it is easy to test."""
    places = [now] * max(1, capacity)
    serving = sorted((v for v in visits if v.status == SERVING), key=lambda v: (v.started_at or v.scheduled_at, v.id))
    waiting = sorted((v for v in visits if v.status in WAITING), key=lambda v: (v.scheduled_at, v.created_at, v.id))
    spots: Dict[str, QueueSpot] = {}
    for v in serving:
        start = v.started_at or v.scheduled_at
        end = max(start + v.duration, now + timedelta(minutes=1))
        i = places.index(min(places))
        places[i] = end
        spots[v.id] = QueueSpot(v.id, IN_PROGRESS, None, 0, len(serving), start, end, 0, 0)
    for n, v in enumerate(waiting):
        i = places.index(min(places))
        start = max(places[i], v.scheduled_at, now)
        end = start + v.duration
        places[i] = end
        wait = max(0, int((start - now).total_seconds() // 60))
        late = max(0, int((start - v.scheduled_at).total_seconds() // 60))
        state = YOUR_TURN if start - now <= YOUR_TURN_WITHIN else WAITING_STATE
        spots[v.id] = QueueSpot(v.id, state, n + 1, n, len(serving), start, end, wait, late)
    return spots


async def day_visits(db: AsyncSession, shop_id: str, day: date, schedule: Schedule) -> List[_Visit]:
    """The shop's visits at the shop on [day] (shop time) that are still waiting or being served."""
    start, end = schedule.day_window(day)
    rows = (
        (
            await db.execute(
                select(Booking).where(
                    Booking.shop_id == shop_id,
                    Booking.service_mode == AT_SHOP,
                    Booking.status.in_((*WAITING, SERVING)),
                    Booking.scheduled_at >= start,
                    Booking.scheduled_at < end,
                )
            )
        )
        .scalars()
        .all()
    )
    started: Dict[str, datetime] = {}
    serving_ids = [b.id for b in rows if b.status == SERVING]
    if serving_ids:
        history = await db.execute(
            select(BookingStatusHistory.booking_id, BookingStatusHistory.created_at).where(
                BookingStatusHistory.booking_id.in_(serving_ids), BookingStatusHistory.to_status == SERVING
            )
        )
        for booking_id, at in history.all():
            at = _utc(at)
            started[booking_id] = max(started.get(booking_id, at), at)  # the latest start, if restarted
    return [
        _Visit(
            id=b.id,
            status=b.status,
            scheduled_at=_utc(b.scheduled_at),
            duration=timedelta(minutes=b.duration_minutes),
            created_at=_utc(b.created_at),
            started_at=started.get(b.id),
        )
        for b in rows
    ]


async def shop_queue(db: AsyncSession, shop_id: str, schedule: Schedule, now: datetime) -> Dict[str, QueueSpot]:
    """Today's queue at the shop, by booking id."""
    today = schedule.local(now).date()
    return compute(await day_visits(db, shop_id, today, schedule), schedule.capacity, now)


async def spot_for(db: AsyncSession, booking: Booking, schedule: Schedule, now: datetime) -> Optional[QueueSpot]:
    """The booking's place in today's queue, or None when it is not in one (another day, finished, not at
    the shop)."""
    if booking.service_mode != AT_SHOP or not booking.shop_id:
        return None
    if schedule.local(_utc(booking.scheduled_at)).date() != schedule.local(now).date():
        return None
    return (await shop_queue(db, booking.shop_id, schedule, now)).get(booking.id)
