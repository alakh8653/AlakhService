"""When a shop can take a booking: inside its opening hours, not on a holiday, not too soon, and below capacity.

Opening hours come from shop_service in shop-local time (IST); bookings are stored in UTC. Everything here
works on aware datetimes and converts at the edges, so a booking at 00:15 IST (18:45 UTC the day before)
lands on the right day and the right interval.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Tuple
from zoneinfo import ZoneInfo

from app.core.fsm import BookingStatus

# Bookings that take up one of the shop's places at their time. OUT_FOR_DELIVERY is left out: the item is
# on its way back, so the shop can take the next customer.
CAPACITY_STATUSES = [
    BookingStatus.PENDING.value,
    BookingStatus.CONFIRMED.value,
    BookingStatus.ASSIGNED.value,
    BookingStatus.PROVIDER_EN_ROUTE.value,
    BookingStatus.PICKED_UP.value,
    BookingStatus.IN_PROGRESS.value,
]

# Opening hours are on a 15-minute grid, so every start time is too.
GRID_MINUTES = 15
LEAD_TIME = timedelta(minutes=30)
MAX_DAYS_AHEAD = 14
DEFAULT_TIMEZONE = "Asia/Kolkata"

# Day statuses of GET /availability.
NOT_CONFIGURED = "NOT_CONFIGURED"  # the shop has not published hours: any future time, as before
AVAILABLE = "AVAILABLE"
CLOSED = "CLOSED"
HOLIDAY = "HOLIDAY"
FULLY_BOOKED = "FULLY_BOOKED"
NO_MORE_TODAY = "NO_MORE_TODAY"

Span = Tuple[datetime, datetime]


def step_minutes(duration: int) -> int:
    """How far apart the offered start times are.

    Half-hourly keeps the list short for the usual 30/60/90-minute services. A service whose length is not
    a multiple of 30 (a 45-minute haircut) gets quarter-hour starts, so back-to-back bookings (10:00, 10:45,
    11:30) are on offer and no gap is left between them.
    """
    return 30 if duration % 30 == 0 else GRID_MINUTES


def _minutes(hhmm: str) -> int:
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


def hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


@dataclass(frozen=True)
class Schedule:
    """A shop's opening hours, as shop_service's GET /shops/{id}/hours reports them."""

    configured: bool
    capacity: int = 1
    # Weekday (0 = Monday) to open intervals, in minutes after local midnight.
    weekly: Dict[int, List[Tuple[int, int]]] = field(default_factory=dict)
    holidays: Dict[date, Optional[str]] = field(default_factory=dict)
    timezone: str = DEFAULT_TIMEZONE

    @classmethod
    def from_shop_service(cls, data: Optional[dict]) -> "Schedule":
        if not data:
            return cls(configured=False)
        weekly = {
            int(d["day"]): sorted((_minutes(i["start"]), _minutes(i["end"])) for i in d.get("intervals") or [])
            for d in data.get("weekly") or []
        }
        holidays = {date.fromisoformat(h["date"]): h.get("note") for h in data.get("holidays") or []}
        return cls(
            configured=bool(data.get("configured")),
            capacity=max(1, int(data.get("capacity") or 1)),
            weekly=weekly,
            holidays=holidays,
            timezone=data.get("timezone") or DEFAULT_TIMEZONE,
        )

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    def intervals_on(self, day: date) -> List[Tuple[int, int]]:
        return [] if day in self.holidays else self.weekly.get(day.weekday(), [])

    def local(self, at: datetime) -> datetime:
        return _utc(at).astimezone(self.zone)

    def at(self, day: date, minutes: int) -> datetime:
        """The UTC instant [minutes] after local midnight of [day] (24:00 is the next midnight)."""
        midnight = datetime.combine(day, time(), tzinfo=self.zone)
        return (midnight + timedelta(minutes=minutes)).astimezone(timezone.utc)

    def day_window(self, day: date) -> Span:
        return self.at(day, 0), self.at(day, 24 * 60)


def _utc(at: datetime) -> datetime:
    # SQLite hands back naive datetimes; they are stored as UTC.
    return at.astimezone(timezone.utc) if at.tzinfo else at.replace(tzinfo=timezone.utc)


def max_concurrent(spans: Iterable[Span], start: datetime, end: datetime) -> int:
    """The most of [spans] running at the same moment within [start, end).

    Not simply how many overlap it: a 10:00-11:00 request next to bookings at 10:00-10:30 and 10:30-11:00
    only ever shares the shop with one of them.
    """
    events = []
    for s, e in spans:
        s, e = max(_utc(s), start), min(_utc(e), end)
        if s < e:
            events += [(s, 1), (e, -1)]
    # At the same instant an ending booking frees its place before the next one takes it.
    events.sort(key=lambda ev: (ev[0], ev[1]))
    running = peak = 0
    for _, delta in events:
        running += delta
        peak = max(peak, running)
    return peak


@dataclass
class Slot:
    start: datetime  # UTC
    time: str  # shop-local "HH:MM"
    remaining: int


@dataclass
class DayAvailability:
    status: str
    slots: List[Slot]
    intervals: List[Tuple[int, int]]
    holiday_note: Optional[str] = None

    @property
    def message(self) -> Optional[str]:
        return {
            CLOSED: "Closed on this day",
            HOLIDAY: "Closed on this day" + (f" ({self.holiday_note})" if self.holiday_note else ""),
            FULLY_BOOKED: "Fully booked — try another day",
            NO_MORE_TODAY: "No more times today — try another day",
        }.get(self.status)


def day_availability(
    schedule: Schedule, day: date, duration: int, now: datetime, booked: Iterable[Span]
) -> DayAvailability:
    """The start times on [day] at which a [duration]-minute booking can be made, with why there are none."""
    if not schedule.configured:
        return DayAvailability(NOT_CONFIGURED, [], [])
    if day in schedule.holidays:
        return DayAvailability(HOLIDAY, [], [], schedule.holidays[day])
    intervals = schedule.intervals_on(day)
    step = step_minutes(duration)
    # Every start whose whole booking fits inside one open interval.
    candidates = [m for s, e in intervals for m in range(s, e - duration + 1, step)]
    if not candidates:
        return DayAvailability(CLOSED, [], intervals)
    earliest = _utc(now) + LEAD_TIME
    booked = list(booked)
    future, slots = 0, []
    for minutes in candidates:
        start = schedule.at(day, minutes)
        if start < earliest:
            continue
        future += 1
        remaining = schedule.capacity - max_concurrent(booked, start, start + timedelta(minutes=duration))
        if remaining > 0:
            slots.append(Slot(start, hhmm(minutes), remaining))
    status = AVAILABLE if slots else FULLY_BOOKED if future else NO_MORE_TODAY
    return DayAvailability(status, slots, intervals)


def booking_problem(
    schedule: Schedule, start: datetime, duration: int, now: datetime, booked: Iterable[Span], grace: timedelta
) -> Optional[str]:
    """Why a booking at [start] cannot be taken, or None when it can (or the shop has no hours)."""
    if not schedule.configured:
        return None
    start = _utc(start)
    local = schedule.local(start)
    day, minutes = local.date(), local.hour * 60 + local.minute
    # "Mon 3 Nov, 9:30 AM"
    label = local.strftime("%a %d %b, %I:%M %p").replace(" 0", " ")
    if day in schedule.holidays:
        note = schedule.holidays[day]
        return f"The shop is closed on {label.split(',')[0]}" + (f" ({note})" if note else "")
    if not any(s <= minutes and minutes + duration <= e for s, e in schedule.intervals_on(day)):
        return f"The shop is not open for the whole of a {duration}-minute booking at {label}; pick another time"
    if local.second or local.microsecond or minutes % GRID_MINUTES:
        return "Booking times start on the quarter hour; pick one of the times offered"
    if start < _utc(now) + LEAD_TIME - grace:
        return f"Book at least {int(LEAD_TIME.total_seconds() // 60)} minutes ahead; pick a later time"
    if max_concurrent(booked, start, start + timedelta(minutes=duration)) >= schedule.capacity:
        return f"{label} is fully booked; pick another time"
    return None
