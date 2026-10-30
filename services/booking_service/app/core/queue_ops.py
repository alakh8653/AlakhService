"""What the shop does to its line on the day: start and finish a service, take walk-ins, mark no-shows.

The rules here are shared by the status endpoint (PUT /bookings/{id}/status) and the queue endpoints
(app/routers/queue.py), so a service started either way is recorded the same way.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import live_queue, metrics, queue_notify
from app.core.availability import Schedule
from app.models.booking import Booking
from app.models.queue import QueueAudit

log = structlog.get_logger()

# A customer may join a shop's line on the day this many times (cancelling and rejoining to jump ahead).
WALK_INS_PER_DAY = 3


async def team_of(lookup_team, shop_id: Optional[str]) -> List[dict]:
    """The shop's team, or none when shop_service cannot say (the queue then uses the shop's capacity)."""
    if not shop_id:
        return []
    try:
        return [m for m in await lookup_team(shop_id) if m.get("id")]
    except Exception as e:  # never let the team lookup break the queue
        log.warning("queue_team_lookup_failed", shop_id=shop_id, error=str(e))
        return []


def can_do(member: dict, service_id: str) -> bool:
    return not member.get("service_ids") or service_id in member["service_ids"]


async def serving_staff(db: AsyncSession, shop_id: str) -> Dict[str, str]:
    """Team members serving someone right now: staff id to booking id."""
    rows = await db.execute(
        select(Booking.served_by_staff_id, Booking.id).where(
            Booking.shop_id == shop_id,
            Booking.status == live_queue.SERVING,
            Booking.served_by_staff_id.is_not(None),
        )
    )
    return {staff: booking_id for staff, booking_id in rows.all()}


async def begin_service(
    db: AsyncSession,
    booking: Booking,
    staff_id: Optional[str],
    team: List[dict],
    spots: Dict[str, live_queue.QueueSpot],
    now: datetime,
) -> None:
    """Records when the service began and who does it: the team member named, else the one the queue
    planned for them if free, else anyone free who does the service (none for a shop without a team).
    The caller flushes; a team member already serving someone fails the unique index (409)."""
    members = {m["id"]: m for m in team}
    if staff_id and staff_id not in members:
        raise ValueError("That team member is not on this shop's team")
    if not staff_id and members:
        busy = await serving_staff(db, booking.shop_id)
        planned = spots.get(booking.id)
        candidates = [planned.worker_id] if planned and planned.worker_id else []
        candidates += sorted(members)
        staff_id = next(
            (s for s in candidates if s in members and s not in busy and can_do(members[s], booking.service_id)),
            None,
        )
    booking.started_at = now
    booking.served_by_staff_id = staff_id
    told = queue_notify.load(booking.queue_notice_state).get("eta")
    error = metrics.record_start(booking.shop_id, datetime.fromisoformat(told) if told else None, now)
    if error is not None:
        log.info("queue_start_error", shop_id=booking.shop_id, booking_id=booking.id, minutes=round(error, 1))


async def finish_service(db: AsyncSession, booking: Booking, now: datetime) -> Optional[float]:
    """Learns the service's length from this visit."""
    settings = await live_queue.settings_for(db, booking.shop_id) if booking.shop_id else live_queue.Settings()
    return await live_queue.record_duration(db, booking, now, settings.alpha)


def open_now(schedule: Schedule, now: datetime) -> bool:
    if not schedule.configured:
        return True
    local = schedule.local(now)
    minute = local.hour * 60 + local.minute
    return any(s <= minute < e for s, e in schedule.intervals_on(local.date()))


async def walk_ins_today(db: AsyncSession, customer_id: str, shop_id: str, schedule: Schedule, now: datetime) -> list:
    start, end = schedule.day_window(schedule.local(now).date())
    rows = await db.execute(
        select(Booking).where(
            Booking.customer_id == customer_id,
            Booking.shop_id == shop_id,
            Booking.source == live_queue.WALK_IN,
            Booking.scheduled_at >= start,  # a walk-in's time is when they joined
            Booking.scheduled_at < end,
        )
    )
    return list(rows.scalars().all())


async def last_joined(db: AsyncSession, shop_id: str) -> Optional[datetime]:
    """When the latest walk-in joined the shop's line."""
    at = (
        await db.execute(
            select(func.max(Booking.created_at)).where(Booking.shop_id == shop_id, Booking.source == live_queue.WALK_IN)
        )
    ).scalar()
    return live_queue._utc(at) if at else None


async def vips_today(db: AsyncSession, shop_id: str, schedule: Schedule, now: datetime) -> int:
    start, _ = schedule.day_window(schedule.local(now).date())
    return (
        await db.execute(
            select(func.count()).where(
                QueueAudit.shop_id == shop_id, QueueAudit.action == "vip", QueueAudit.created_at >= start
            )
        )
    ).scalar() or 0


def no_show_problem(booking: Booking, settings: live_queue.Settings, now: datetime) -> Optional[str]:
    """Why the booking cannot be marked a no-show yet, if it cannot."""
    if booking.status not in live_queue.WAITING:
        return "Only a customer still waiting can be marked a no-show"
    if booking.source == live_queue.WALK_IN:
        return "A walk-in who left can simply be cancelled"
    if booking.checked_in_at is not None:
        return "The customer has checked in"
    due = live_queue._utc(booking.scheduled_at) + timedelta(minutes=settings.grace_minutes)
    if now < due:
        return f"Wait until {settings.grace_minutes} minutes after their time before marking a no-show"
    return None
