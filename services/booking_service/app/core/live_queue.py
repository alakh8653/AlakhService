"""The live queue at a shop today: each customer's place in line, how long until their turn, how late it runs.

Many customers can book the same time at a shop that serves several at once. On the day a shop runs behind
when services overrun or start late, so the booked time alone does not tell a customer when they will be
seen. The queue works it out from what is happening now, with the queue engine (app/core/queue_engine.py):

- the workers are the shop's team (each doing the services they are listed for), or, for a shop without a
  team, [capacity] places that do everything. A team member on a break or off today (set by the shop)
  takes nobody until they are back. They work the shop's opening hours, plus OVERTIME for those already
  in the line at closing;
- a customer being served holds their worker until the start plus the service's learnt length, and never
  less than a minute from now while they are still in it;
- everyone else waiting today goes by priority (VIP, appointment, walk-in; a long wait moves a customer
  up), then by booked time and who booked first; a shop can also move people by hand. Someone who asked
  for a team member waits for them while that person works today;
- service lengths are learnt from completed visits (record_duration), per service and team member, so
  the estimate follows how long the shop really takes. Each start comes with a range (eta_min..eta_max).

A customer who must check in (the shop's setting) and has not, past their grace period, is out of the line
(CHECK_IN_NEEDED) until they do; checking in late puts them in at the time they arrived.

It is an estimate: the shop may take someone early or late. It is recomputed on every look.
"""

import json
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Sequence, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import queue_engine as qe
from app.core.availability import Schedule
from app.core.fsm import AT_SHOP, BookingStatus
from app.models.booking import Booking, BookingStatusHistory
from app.models.queue import DurationStat, QueueAudit, QueueSettings, WorkerStatus

# Still to be seen today: requested, confirmed, or given to a provider, and not started.
WAITING = (BookingStatus.PENDING.value, BookingStatus.CONFIRMED.value, BookingStatus.ASSIGNED.value)
SERVING = BookingStatus.IN_PROGRESS.value
# Within this of their estimated start, a waiting customer is told it is their turn.
YOUR_TURN_WITHIN = timedelta(minutes=2)
# Those already in the line at closing are still served, up to this long after.
OVERTIME = timedelta(minutes=90)
# A learnt length counts for one team member after this many of their visits (before: the shop's).
STAFF_MIN_SAMPLES = 3
# Actual durations outside this share of the nominal are mistakes (a start or finish pressed late).
PLAUSIBLE = (0.25, 4.0)
NO_SHOW_REASON = "No-show"
WALK_IN, BOOKED = "WALK_IN", "BOOKED"
# The customer id of a walk-in the shop added without an account (nobody to notify).
WALK_IN_PREFIX = "walk-in:"
PRIORITY_NAMES = {qe.VIP: "VIP", qe.APPOINTMENT: "APPOINTMENT", qe.WALK_IN: "WALK_IN"}

WAITING_STATE, YOUR_TURN, IN_PROGRESS, NOT_TODAY, NOT_QUEUED = (
    "WAITING",
    "YOUR_TURN",
    "IN_PROGRESS",
    "NOT_TODAY",
    "NOT_QUEUED",
)
# Nobody on today's team does it, or not before closing; or they have to check in first.
UNSERVABLE, CHECK_IN_NEEDED = "UNSERVABLE", "CHECK_IN_NEEDED"


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
    estimated_start: Optional[datetime]
    estimated_end: Optional[datetime]
    wait_minutes: Optional[int]
    running_late_minutes: int
    # The likely range of the start, and how sure it is (HIGH, MEDIUM, LOW).
    eta_min: Optional[datetime] = None
    eta_max: Optional[datetime] = None
    confidence: Optional[str] = None
    # The team member expected to serve them (a place number for a shop without a team).
    worker_id: Optional[str] = None
    # Jobs before theirs with that worker.
    ahead_on_worker: int = 0
    # Why they cannot be served today (NO_ELIGIBLE_WORKER, BEYOND_SHIFT), or that their pick is away.
    reason: Optional[str] = None
    # Being served for much longer than planned.
    overrun: bool = False


@dataclass
class _Visit:
    id: str
    status: str
    scheduled_at: datetime
    duration: timedelta
    created_at: datetime
    started_at: Optional[datetime] = None
    service_id: Optional[str] = None
    source: str = BOOKED
    priority: int = qe.APPOINTMENT
    checked_in_at: Optional[datetime] = None
    rank: Optional[float] = None
    served_by: Optional[str] = None
    preferred_staff_id: Optional[str] = None


@dataclass
class Settings:
    buffer_pct: float = 0.0
    alpha: float = 0.2  # tuned with tools/queue_sim.py (0.1-0.2 beat 0.3 and 0.5)
    grace_minutes: int = 10
    aging_minutes: int = 20
    check_in_required: bool = False
    vip_per_day: int = 5


@dataclass
class Day:
    """Everything the queue needs for one shop's day (loaded by load_day)."""

    visits: List[_Visit]
    capacity: int
    team: List[dict]
    statuses: Dict[str, Tuple[str, Optional[datetime]]]
    settings: Settings
    stats: Dict[Tuple[str, str], qe.DurationModel]
    shifts: List[qe.Span]
    no_show_rate: float = 0.0


def _shifts(schedule: Optional[Schedule], day: Optional[date], now: datetime) -> List[qe.Span]:
    if schedule is None or not schedule.configured or day is None:
        return [(now - timedelta(days=1), now + timedelta(days=1))]
    spans = [(schedule.at(day, s), schedule.at(day, e)) for s, e in schedule.intervals_on(day)]
    if spans:
        spans[-1] = (spans[-1][0], spans[-1][1] + OVERTIME)
    return spans


def _durations(visits: Sequence[_Visit], stats: Dict[Tuple[str, str], qe.DurationModel], per_visit: bool):
    """Each service's learnt length: the team member's once they have enough visits, else the shop's, else
    the catalogue's (with a 20% spread until there is data)."""
    nominal = {(v.id if per_visit else v.service_id or v.id): v.duration.total_seconds() / 60 for v in visits}

    def look(service_id: str, worker_id: Optional[str]) -> qe.DurationModel:
        own = stats.get((service_id, worker_id or ""))
        if own and own.n >= STAFF_MIN_SAMPLES:
            return own
        shop = stats.get((service_id, ""))
        if shop and shop.n:
            return shop
        minutes = nominal.get(service_id, 30.0)
        return qe.DurationModel(minutes, (0.2 * minutes) ** 2, 0)

    return look


def predict_day(day: Day, now: datetime, per_visit: bool = False) -> Dict[str, QueueSpot]:
    """The queue for one shop's day (see the module docstring). Pure, so it is easy to test."""
    s = day.settings
    cfg = qe.Config(
        buffer_pct=s.buffer_pct,
        aging_minutes=s.aging_minutes,
        no_show_rate=day.no_show_rate,
        your_turn_within=int(YOUR_TURN_WITHIN.total_seconds() // 60),
    )
    if day.team:
        workers = []
        for m in sorted(day.team, key=lambda m: m["id"]):
            status, until = day.statuses.get(m["id"], (qe.AVAILABLE, None))
            if status == qe.ON_BREAK and until is not None and until <= now:
                status, until = qe.AVAILABLE, None
            skills = frozenset(m.get("service_ids") or []) or None
            workers.append(qe.Worker(m["id"], skills, status, until, list(day.shifts)))
    else:
        workers = [qe.Worker(f"place-{i + 1}", None, shifts=list(day.shifts)) for i in range(max(1, day.capacity))]
    ids = {w.id for w in workers}
    grace = timedelta(minutes=s.grace_minutes)
    serving = sorted(
        (v for v in day.visits if v.status == SERVING), key=lambda v: (v.started_at or v.scheduled_at, v.id)
    )
    # Those started without saying who serves them go to whoever is free (one each, then round again).
    busy: Dict[str, int] = {w.id: 0 for w in workers}
    for v in serving:
        if v.served_by in ids:
            busy[v.served_by] += 1
    entries: List[qe.Entry] = []
    held: Dict[str, QueueSpot] = {}
    for v in serving:
        worker = v.served_by if v.served_by in ids else min(busy, key=lambda w: (busy[w], w))
        if v.served_by not in ids:
            busy[worker] += 1
        entries.append(
            qe.Entry(
                v.id,
                v.id if per_visit else v.service_id or v.id,
                v.priority,
                v.scheduled_at,
                v.created_at,
                state=qe.SERVING,
                worker_id=worker,
                started_at=v.started_at or v.scheduled_at,
            )
        )
    for v in day.visits:
        if v.status not in WAITING:
            continue
        if v.source == WALK_IN:
            ready = v.checked_in_at or v.created_at
        elif v.checked_in_at and v.checked_in_at > v.scheduled_at + grace:
            ready = v.checked_in_at  # late: in the line from when they arrived
        elif s.check_in_required and not v.checked_in_at and now > v.scheduled_at + grace:
            held[v.id] = QueueSpot(v.id, CHECK_IN_NEEDED, None, 0, len(serving), None, None, None, 0)
            continue
        else:
            ready = v.scheduled_at
        entries.append(
            qe.Entry(
                v.id,
                v.id if per_visit else v.service_id or v.id,
                qe.WALK_IN if v.source == WALK_IN and v.priority == qe.APPOINTMENT else v.priority,
                ready,
                v.created_at,
                customer_key=v.id,
                preferred_worker_id=v.preferred_staff_id if v.preferred_staff_id in ids else None,
                rank=v.rank,
                scheduled_at=None if v.source == WALK_IN else v.scheduled_at,
            )
        )
    durations = _durations(day.visits, day.stats, per_visit)
    predictions = qe.predict(now, workers, entries, cfg, durations)
    spots: Dict[str, QueueSpot] = dict(held)
    for e in entries:
        p = predictions[e.id]
        if p.state == qe.SERVING:
            spots[e.id] = QueueSpot(
                e.id, IN_PROGRESS, None, 0, len(serving), p.start, p.eta_max, 0, 0,
                worker_id=p.worker_id, overrun=p.overrun, confidence=p.confidence,
            )  # fmt: skip
        elif p.state == "UNSERVABLE":
            spots[e.id] = QueueSpot(e.id, UNSERVABLE, None, 0, len(serving), None, None, None, 0, reason=p.reason)
        else:
            planned = durations(e.service_id, p.worker_id).mean * (1 + cfg.buffer_pct)
            spots[e.id] = QueueSpot(
                e.id,
                p.state,
                p.position,
                p.people_ahead,
                len(serving),
                p.start,
                p.start + timedelta(minutes=planned),
                max(0, int((p.start - now).total_seconds() // 60)),
                p.running_late_minutes,
                eta_min=p.eta_min,
                eta_max=p.eta_max,
                confidence=p.confidence,
                worker_id=p.worker_id,
                ahead_on_worker=p.ahead_on_worker,
                reason=p.reason,
            )
    return spots


def compute(visits: List[_Visit], capacity: int, now: datetime) -> Dict[str, QueueSpot]:
    """The queue for [capacity] places that do everything, each visit as long as booked (no team, no
    learnt lengths)."""
    for v in visits:
        v.duration = v.duration  # booked length per visit
    day = Day(list(visits), capacity, [], {}, Settings(), {}, _shifts(None, None, now))
    return predict_day(day, now, per_visit=True)


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
    serving_ids = [b.id for b in rows if b.status == SERVING and b.started_at is None]
    if serving_ids:  # started before the start time was kept on the booking
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
            started_at=_utc(b.started_at) if b.started_at else started.get(b.id),
            service_id=b.service_id,
            source=b.source or BOOKED,
            priority=b.priority if b.priority is not None else qe.APPOINTMENT,
            checked_in_at=_utc(b.checked_in_at) if b.checked_in_at else None,
            rank=b.queue_rank,
            served_by=b.served_by_staff_id,
            preferred_staff_id=b.preferred_staff_id,
        )
        for b in rows
    ]


async def settings_for(db: AsyncSession, shop_id: str) -> Settings:
    row = await db.get(QueueSettings, shop_id)
    if row is None:
        return Settings()
    return Settings(
        row.buffer_pct, row.alpha, row.grace_minutes, row.aging_minutes, bool(row.check_in_required), row.vip_per_day
    )


async def save_settings(db: AsyncSession, shop_id: str, values: dict) -> Settings:
    row = await db.get(QueueSettings, shop_id)
    if row is None:
        row = QueueSettings(shop_id=shop_id, **Settings().__dict__)
        db.add(row)
    for k, v in values.items():
        setattr(row, k, v)
    row.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return await settings_for(db, shop_id)


async def statuses_for(
    db: AsyncSession, shop_id: str, schedule: Schedule, now: datetime
) -> Dict[str, Tuple[str, Optional[datetime]]]:
    """Today's team status set by the shop (a status from an earlier day no longer counts)."""
    day_start, _ = schedule.day_window(schedule.local(now).date())
    rows = (await db.execute(select(WorkerStatus).where(WorkerStatus.shop_id == shop_id))).scalars().all()
    return {r.staff_id: (r.status, _utc(r.until) if r.until else None) for r in rows if _utc(r.updated_at) >= day_start}


async def set_status(
    db: AsyncSession,
    shop_id: str,
    staff_id: str,
    status: str,
    until: Optional[datetime],
    actor_id: str,
    at: Optional[datetime] = None,
) -> None:
    row = await db.get(WorkerStatus, (shop_id, staff_id))
    if row is None:
        row = WorkerStatus(shop_id=shop_id, staff_id=staff_id, status=status)
        db.add(row)
    at = at or datetime.now(timezone.utc)
    row.status, row.until, row.updated_at = status, until, at
    await audit(
        db, shop_id, None, "staff_status", actor_id, {"staff_id": staff_id, "status": status, "until": until}, at
    )


async def stats_for(db: AsyncSession, shop_id: str) -> Dict[Tuple[str, str], qe.DurationModel]:
    rows = (await db.execute(select(DurationStat).where(DurationStat.shop_id == shop_id))).scalars().all()
    return {(r.service_id, r.staff_id): qe.DurationModel(r.mean, r.var, r.n) for r in rows}


async def record_duration(db: AsyncSession, booking: Booking, completed_at: datetime, alpha: float) -> Optional[float]:
    """Learns from a finished visit: its actual length updates the service's average for the shop and for
    the team member who served it. Returns the minutes counted (None when it was not plausible)."""
    if not booking.shop_id or booking.service_mode != AT_SHOP:
        return None
    started = booking.started_at
    if started is None:
        started = (
            await db.execute(
                select(func.max(BookingStatusHistory.created_at)).where(
                    BookingStatusHistory.booking_id == booking.id, BookingStatusHistory.to_status == SERVING
                )
            )
        ).scalar()
    if started is None:
        return None
    actual = (completed_at - _utc(started)).total_seconds() / 60
    nominal = booking.duration_minutes or 30
    if not PLAUSIBLE[0] * nominal <= actual <= PLAUSIBLE[1] * nominal:
        return None
    for staff in {"", booking.served_by_staff_id or ""}:
        row = await db.get(DurationStat, (booking.shop_id, booking.service_id, staff))
        model = qe.DurationModel(nominal, 0.0, 0) if row is None else qe.DurationModel(row.mean, row.var, row.n)
        model = model.update(actual, alpha)
        if row is None:
            row = DurationStat(shop_id=booking.shop_id, service_id=booking.service_id, staff_id=staff)
            db.add(row)
        row.mean, row.var, row.n, row.updated_at = model.mean, model.var, model.n, datetime.now(timezone.utc)
    await db.flush()
    return actual


async def no_show_rate(db: AsyncSession, shop_id: str, now: datetime) -> float:
    """The share of the shop's visits in the last 30 days that were no-shows (pulls the low end of each
    range earlier: some of those ahead will not come)."""
    since = now - timedelta(days=30)
    base = select(func.count()).where(
        Booking.shop_id == shop_id, Booking.service_mode == AT_SHOP, Booking.scheduled_at >= since,
        Booking.scheduled_at < now,
    )  # fmt: skip
    total = (await db.execute(base)).scalar() or 0
    if total < 20:  # too few to say
        return 0.0
    missed = (await db.execute(base.where(Booking.cancellation_reason == NO_SHOW_REASON))).scalar() or 0
    return min(0.5, missed / total)


async def audit(
    db: AsyncSession,
    shop_id: str,
    booking_id: Optional[str],
    action: str,
    actor_id: str,
    detail=None,
    at: Optional[datetime] = None,
):
    db.add(
        QueueAudit(
            id=str(uuid.uuid4()),
            shop_id=shop_id,
            booking_id=booking_id,
            action=action,
            actor_id=actor_id or "system",
            detail=json.dumps(detail, default=str) if detail is not None else None,
            created_at=at or datetime.now(timezone.utc),
        )
    )
    await db.flush()


async def load_day(
    db: AsyncSession, shop_id: str, schedule: Schedule, now: datetime, team: Optional[List[dict]] = None
) -> Day:
    today = schedule.local(now).date()
    return Day(
        visits=await day_visits(db, shop_id, today, schedule),
        capacity=schedule.capacity,
        team=[m for m in team or [] if m.get("id")],
        statuses=await statuses_for(db, shop_id, schedule, now),
        settings=await settings_for(db, shop_id),
        stats=await stats_for(db, shop_id),
        shifts=_shifts(schedule, today, now),
        no_show_rate=await no_show_rate(db, shop_id, now),
    )


async def shop_queue(
    db: AsyncSession, shop_id: str, schedule: Schedule, now: datetime, team: Optional[List[dict]] = None
) -> Dict[str, QueueSpot]:
    """Today's queue at the shop, by booking id."""
    return predict_day(await load_day(db, shop_id, schedule, now, team), now)


async def spot_for(
    db: AsyncSession, booking: Booking, schedule: Schedule, now: datetime, team: Optional[List[dict]] = None
) -> Optional[QueueSpot]:
    """The booking's place in today's queue, or None when it is not in one (another day, finished, not at
    the shop)."""
    if booking.service_mode != AT_SHOP or not booking.shop_id:
        return None
    if schedule.local(_utc(booking.scheduled_at)).date() != schedule.local(now).date():
        return None
    return (await shop_queue(db, booking.shop_id, schedule, now, team)).get(booking.id)
