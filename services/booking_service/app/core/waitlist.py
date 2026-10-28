"""The waitlist: customers who wanted a day at a shop that was full, told once when a time there opens up.

A time opens up when a booking at the shop that day is cancelled, expires unconfirmed, or is moved to
another day. Everyone waiting for that shop and day is told at once (whoever books first gets it); each
entry is told once, and the customer can join again if they miss it. Days are in DISPLAY_TIMEZONE, the
time zone the platform shows (shops are in India).
"""

import uuid
from datetime import date, datetime, timezone
from typing import List, Optional
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.waitlist import WaitlistEntry

log = structlog.get_logger()

# Enough for anyone's plans; stops one account from waiting on every day of every shop.
MAX_WAITING = 10


def local_day(at: datetime) -> date:
    at = at if at.tzinfo else at.replace(tzinfo=timezone.utc)
    return at.astimezone(ZoneInfo(settings.DISPLAY_TIMEZONE)).date()


def today() -> date:
    return local_day(datetime.now(timezone.utc))


async def waiting(db: AsyncSession, customer_id: str) -> List[WaitlistEntry]:
    """The customer's entries for today or later that have not been told yet."""
    result = await db.execute(
        select(WaitlistEntry)
        .where(
            WaitlistEntry.customer_id == customer_id, WaitlistEntry.day >= today(), WaitlistEntry.notified_at.is_(None)
        )
        .order_by(WaitlistEntry.day, WaitlistEntry.created_at)
    )
    return list(result.scalars().all())


async def join(db: AsyncSession, customer_id: str, service_id: str, shop_id: str, day: date) -> WaitlistEntry:
    """Adds the customer for [day] (joining again after being told starts a new wait). ValueError says why not."""
    if day < today():
        raise ValueError("That day has passed")
    existing = (
        await db.execute(
            select(WaitlistEntry).where(
                WaitlistEntry.customer_id == customer_id,
                WaitlistEntry.service_id == service_id,
                WaitlistEntry.day == day,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.notified_at = None  # waiting again
        await db.flush()
        return existing
    if len(await waiting(db, customer_id)) >= MAX_WAITING:
        raise ValueError(f"You can wait for up to {MAX_WAITING} days at a time")
    entry = WaitlistEntry(
        id=str(uuid.uuid4()),
        customer_id=customer_id,
        service_id=service_id,
        shop_id=shop_id,
        day=day,
        created_at=datetime.now(timezone.utc),
    )
    db.add(entry)
    await db.flush()
    return entry


async def time_opened(
    db: AsyncSession, shop_id: Optional[str], at: datetime, except_customer: Optional[str] = None
) -> List[WaitlistEntry]:
    """A time at [shop_id] on the day of [at] opened up: the entries waiting for it, marked told (the
    caller tells them after committing). The customer who freed it is not told about their own time."""
    if not shop_id:
        return []
    day = local_day(at)
    if day < today():
        return []
    query = select(WaitlistEntry).where(
        WaitlistEntry.shop_id == shop_id, WaitlistEntry.day == day, WaitlistEntry.notified_at.is_(None)
    )
    if db.get_bind().dialect.name == "postgresql":
        query = query.with_for_update(skip_locked=True)
    entries = [e for e in (await db.execute(query)).scalars().all() if e.customer_id != except_customer]
    now = datetime.now(timezone.utc)
    for e in entries:
        e.notified_at = now
    await db.flush()
    if entries:
        log.info("waitlist_time_opened", shop_id=shop_id, day=day.isoformat(), waiting=len(entries))
    return entries


async def tell(notifier, entries: List[WaitlistEntry]) -> None:
    """Sends waitlist.time_opened to each customer (after the change is committed)."""
    for e in entries:
        await notifier.send(
            "waitlist.time_opened",
            [{"user_id": e.customer_id, "role": "customer"}],
            {"service_id": e.service_id, "shop_id": e.shop_id, "date": e.day.strftime("%d %b")},
        )
