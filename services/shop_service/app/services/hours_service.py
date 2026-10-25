"""Reads and writes a shop's opening hours, holidays and capacity."""

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hours import ShopHoliday, ShopScheduleSettings
from app.models.shop import ShopHours, StaffMember
from app.schemas.hours import DayHours, Holiday, Interval, ShopSchedule, to_minutes

# Shops are in India. IST has no daylight saving, so a fixed offset is exact (and needs no tz database).
SHOP_TIMEZONE = "Asia/Kolkata"
IST = timezone(timedelta(hours=5, minutes=30))


class HolidayExistsError(Exception):
    pass


def today_in_shop_zone() -> date:
    return datetime.now(IST).date()


async def _settings(db: AsyncSession, shop_id: str) -> Optional[ShopScheduleSettings]:
    return await db.get(ShopScheduleSettings, shop_id)


async def _settings_for_update(db: AsyncSession, shop_id: str) -> ShopScheduleSettings:
    row = await _settings(db, shop_id)
    if row is None:
        row = ShopScheduleSettings(shop_id=shop_id, hours_configured=False)
        db.add(row)
    row.updated_at = datetime.now(timezone.utc)
    return row


async def get_schedule(db: AsyncSession, shop_id: str) -> ShopSchedule:
    settings = await _settings(db, shop_id)
    rows = (await db.execute(select(ShopHours).where(ShopHours.shop_id == shop_id))).scalars().all()
    by_day = {day: [] for day in range(7)}
    for row in sorted(rows, key=lambda r: (r.day_of_week, to_minutes(r.open_time))):
        by_day[row.day_of_week].append(Interval(start=row.open_time, end=row.close_time))
    holidays = (
        await db.execute(
            select(ShopHoliday)
            .where(ShopHoliday.shop_id == shop_id, ShopHoliday.date >= today_in_shop_zone())
            .order_by(ShopHoliday.date)
        )
    ).scalars()
    active_staff = (
        await db.execute(
            select(func.count())
            .select_from(StaffMember)
            .where(StaffMember.shop_id == shop_id, StaffMember.is_active == True)  # noqa: E712
        )
    ).scalar() or 0
    override = settings.capacity if settings else None
    return ShopSchedule(
        shop_id=shop_id,
        timezone=SHOP_TIMEZONE,
        configured=bool(settings and settings.hours_configured),
        weekly=[DayHours(day=day, intervals=intervals) for day, intervals in by_day.items()],
        holidays=[Holiday(date=h.date, note=h.note) for h in holidays],
        capacity=override or max(1, active_staff),
        capacity_override=override,
        active_staff=active_staff,
        updated_at=settings.updated_at if settings else None,
    )


async def set_weekly_hours(db: AsyncSession, shop_id: str, weekly: list[DayHours]) -> None:
    """Replaces the whole week; days not listed are closed."""
    await db.execute(delete(ShopHours).where(ShopHours.shop_id == shop_id))
    for day in weekly:
        for interval in day.intervals:
            db.add(
                ShopHours(
                    id=str(uuid.uuid4()),
                    shop_id=shop_id,
                    day_of_week=day.day,
                    open_time=interval.start,
                    close_time=interval.end,
                )
            )
    (await _settings_for_update(db, shop_id)).hours_configured = True
    await db.flush()


async def set_capacity(db: AsyncSession, shop_id: str, capacity: Optional[int]) -> None:
    (await _settings_for_update(db, shop_id)).capacity = capacity
    await db.flush()


async def add_holiday(db: AsyncSession, shop_id: str, day: date, note: Optional[str]) -> None:
    existing = await db.execute(select(ShopHoliday.id).where(ShopHoliday.shop_id == shop_id, ShopHoliday.date == day))
    if existing.scalar_one_or_none() is not None:
        raise HolidayExistsError()
    db.add(ShopHoliday(id=str(uuid.uuid4()), shop_id=shop_id, date=day, note=note))
    await _settings_for_update(db, shop_id)
    try:
        await db.flush()
    except IntegrityError:  # the same date added twice at once
        await db.rollback()
        raise HolidayExistsError() from None


async def remove_holiday(db: AsyncSession, shop_id: str, day: date) -> bool:
    result = await db.execute(delete(ShopHoliday).where(ShopHoliday.shop_id == shop_id, ShopHoliday.date == day))
    if result.rowcount:
        await _settings_for_update(db, shop_id)
        await db.flush()
    return bool(result.rowcount)
