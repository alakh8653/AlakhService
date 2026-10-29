"""Home visits: when the professional will reach each customer's door today.

A provider's home visits for the day form a route: whatever they are doing now, then the visit they are
on the way to, then the rest in booked order. Each arrival is the later of the booked time (nobody is
visited early) and the end of the job before plus the travel between the two addresses:

  travel = straight-line distance x ROAD_FACTOR at SPEED_KMH, plus PARKING_MINUTES, within [5, 120] min;
  DEFAULT_TRAVEL_MINUTES when either place has no coordinates.

A job in progress ends at its start plus its length, and never less than a minute from now (an overrun
pushes the rest of the route). Each arrival comes with a range: the further down the route, the wider
(travel and the jobs before can each run long). The route is recomputed on every look, so a professional
delayed at one door moves every later arrival at once.
"""

import math
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Awaitable, Callable, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.fsm import AT_HOME, BookingStatus
from app.models.booking import Booking, BookingStatusHistory

Point = Tuple[float, float]
LocationLookup = Callable[[str, str], Awaitable[Optional[Point]]]

ROAD_FACTOR = 1.4
SPEED_KMH = 25.0
PARKING_MINUTES = 3
DEFAULT_TRAVEL_MINUTES = 20
ASSIGNED, EN_ROUTE, SERVING = (
    BookingStatus.ASSIGNED.value,
    BookingStatus.PROVIDER_EN_ROUTE.value,
    BookingStatus.IN_PROGRESS.value,
)
ON_ROUTE = (ASSIGNED, EN_ROUTE, SERVING)
# What a customer sees: the professional is planned, on the way, or with them.
PLANNED, ON_THE_WAY, ARRIVED = "PLANNED", "ON_THE_WAY", "ARRIVED"


def _utc(at: datetime) -> datetime:
    return at.astimezone(timezone.utc) if at.tzinfo else at.replace(tzinfo=timezone.utc)


def day_window(now: datetime, zone: str) -> Tuple[datetime, datetime]:
    """Today in [zone], as UTC instants."""
    local = now.astimezone(ZoneInfo(zone)).date()
    start = datetime.combine(local, time(), tzinfo=ZoneInfo(zone)).astimezone(timezone.utc)
    return start, start + timedelta(days=1)


def eta_text(at: datetime, zone: str) -> str:
    return at.astimezone(ZoneInfo(zone)).strftime("%I:%M %p").lstrip("0")


def travel_minutes(a: Optional[Point], b: Optional[Point]) -> float:
    """Minutes to drive from [a] to [b] in town (haversine x road factor at city speed, plus parking)."""
    if a is None or b is None:
        return float(DEFAULT_TRAVEL_MINUTES)
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    km = 2 * 6371 * math.asin(math.sqrt(h))
    return min(120.0, max(5.0, km * ROAD_FACTOR / SPEED_KMH * 60 + PARKING_MINUTES))


@dataclass
class Visit:
    id: str
    status: str
    scheduled_at: datetime
    minutes: int
    location: Optional[Point] = None
    # When they set off for it (PROVIDER_EN_ROUTE) and began (IN_PROGRESS).
    left_at: Optional[datetime] = None
    started_at: Optional[datetime] = None


@dataclass
class Arrival:
    booking_id: str
    state: str
    arrive_at: datetime
    arrive_min: datetime
    arrive_max: datetime
    # The drive to this door, and the visits before it on today's route.
    travel_minutes: int
    jobs_before: int
    # When they should set off, and how far behind the booked time they will be.
    leave_at: datetime
    late_minutes: int
    finish_at: datetime


def plan(visits: List[Visit], origin: Optional[Point], now: datetime) -> Dict[str, Arrival]:
    """Today's route for one professional. Pure; O(V log V)."""
    rank = {SERVING: 0, EN_ROUTE: 1, ASSIGNED: 2}
    route = sorted(visits, key=lambda v: (rank.get(v.status, 3), v.scheduled_at, v.id))
    free, here = now, origin
    spread = 0.0  # minutes of doubt that build up along the route
    out: Dict[str, Arrival] = {}
    for n, v in enumerate(route):
        length = timedelta(minutes=v.minutes)
        if v.status == SERVING:
            began = v.started_at or v.scheduled_at
            finish = max(began + length, now + timedelta(minutes=1))
            arrive, drive, state, leave = began, 0.0, ARRIVED, began
            spread += 0.15 * v.minutes
        else:
            drive = float(round(travel_minutes(here, v.location)))  # whole minutes: times people read
            if v.status == EN_ROUTE:
                left = v.left_at or now
                arrive = max(now + timedelta(minutes=1), left + timedelta(minutes=drive), free)
                state, leave = ON_THE_WAY, left
            else:
                arrive = max(v.scheduled_at, free + timedelta(minutes=drive))
                state, leave = PLANNED, arrive - timedelta(minutes=drive)
            spread += 5 + 0.25 * drive
            finish = arrive + length
        doubt = timedelta(minutes=min(60.0, spread))
        out[v.id] = Arrival(
            booking_id=v.id,
            state=state,
            arrive_at=arrive,
            arrive_min=max(now, arrive - doubt * 0.4) if state != ARRIVED else arrive,
            arrive_max=arrive + doubt if state != ARRIVED else arrive,
            travel_minutes=round(drive),
            jobs_before=n,
            leave_at=leave,
            late_minutes=max(0, int((arrive - v.scheduled_at).total_seconds() // 60)),
            finish_at=finish,
        )
        if state != ARRIVED:
            spread += 0.15 * v.minutes
        free, here = finish, v.location
    return out


async def provider_day(db: AsyncSession, provider_id: str, day_start: datetime, day_end: datetime) -> List[Booking]:
    """The provider's home visits on the day that are still to do or under way."""
    rows = await db.execute(
        select(Booking).where(
            Booking.provider_id == provider_id,
            Booking.service_mode == AT_HOME,
            Booking.status.in_(ON_ROUTE),
            Booking.scheduled_at >= day_start,
            Booking.scheduled_at < day_end,
        )
    )
    return list(rows.scalars().all())


async def route_for(
    db: AsyncSession,
    provider_id: str,
    day: Tuple[datetime, datetime],
    now: datetime,
    lookup_location: LocationLookup,
) -> Tuple[List[Booking], Dict[str, Arrival]]:
    """The provider's route today: their bookings and when they reach each one."""
    bookings = await provider_day(db, provider_id, *day)
    if not bookings:
        return [], {}
    ids = [b.id for b in bookings]
    moments: Dict[Tuple[str, str], datetime] = {}
    history = await db.execute(
        select(BookingStatusHistory.booking_id, BookingStatusHistory.to_status, BookingStatusHistory.created_at).where(
            BookingStatusHistory.booking_id.in_(ids), BookingStatusHistory.to_status.in_((EN_ROUTE, SERVING))
        )
    )
    for booking_id, status, at in history.all():
        at = _utc(at)
        if not day[0] <= at <= now:  # only today's moves count (and none from a clock ahead of ours)
            continue
        key = (booking_id, status)
        moments[key] = max(moments.get(key, at), at)
    origin = None
    shop_ids = {b.shop_id for b in bookings if b.shop_id}
    if shop_ids:  # they set off from the shop
        origin = await _safe(lookup_location("shop", sorted(shop_ids)[0]))
    visits = []
    for b in bookings:
        where = await _safe(lookup_location("address", b.address_id)) if b.address_id else None
        visits.append(
            Visit(
                id=b.id,
                status=b.status,
                scheduled_at=_utc(b.scheduled_at),
                minutes=b.duration_minutes,
                location=where,
                left_at=moments.get((b.id, EN_ROUTE)),
                started_at=_utc(b.started_at) if b.started_at else moments.get((b.id, SERVING)),
            )
        )
    return bookings, plan(visits, origin, now)


async def _safe(lookup: Awaitable[Optional[Point]]) -> Optional[Point]:
    try:
        return await lookup
    except Exception:  # an unknown place just uses the default travel time
        return None
