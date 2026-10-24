"""Opening hours, holidays and capacity: what customers can book and when (times are shop-local, IST)."""

import re
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# Bookable times start on the quarter hour, so hours are kept to the same grid.
GRANULARITY_MINUTES = 15
MAX_INTERVALS_PER_DAY = 4
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

_TIME = re.compile(r"^(\d{2}):(\d{2})$")


def to_minutes(value: str) -> int:
    """Minutes after midnight of "HH:MM"; "24:00" is the end of the day."""
    match = _TIME.match(value)
    if not match:
        raise ValueError(f"{value!r} is not a time like 09:30")
    hours, minutes = int(match[1]), int(match[2])
    if minutes > 59 or hours > 24 or (hours == 24 and minutes):
        raise ValueError(f"{value!r} is not a time of day")
    if minutes % GRANULARITY_MINUTES:
        raise ValueError(f"{value} must be on the quarter hour (:00, :15, :30 or :45)")
    return hours * 60 + minutes


class Interval(BaseModel):
    start: str
    end: str

    @model_validator(mode="after")
    def start_before_end(self):
        if to_minutes(self.start) == 24 * 60:
            raise ValueError("an interval cannot start at 24:00")
        if to_minutes(self.start) >= to_minutes(self.end):
            # Overnight hours (e.g. 22:00-02:00) are two intervals on two days.
            raise ValueError(f"{self.start}-{self.end}: the opening time must be before the closing time")
        return self


class DayHours(BaseModel):
    day: int = Field(ge=0, le=6, description="0 = Monday … 6 = Sunday")
    # Empty means closed that day.
    intervals: List[Interval] = Field(default_factory=list, max_length=MAX_INTERVALS_PER_DAY)

    @model_validator(mode="after")
    def no_overlaps(self):
        ordered = sorted(self.intervals, key=lambda i: to_minutes(i.start))
        for earlier, later in zip(ordered, ordered[1:], strict=False):
            # Touching intervals are refused too: they are one interval, and split in two a booking
            # spanning the join would not fit either half.
            if to_minutes(later.start) <= to_minutes(earlier.end):
                raise ValueError(
                    f"{DAY_NAMES[self.day]}: {earlier.start}-{earlier.end} and {later.start}-{later.end} "
                    "overlap or touch; merge them into one"
                )
        self.intervals = ordered
        return self


class WeeklyHoursUpdate(BaseModel):
    # Days left out are closed.
    weekly: List[DayHours] = Field(max_length=7)

    @field_validator("weekly")
    @classmethod
    def one_entry_per_day(cls, days: List[DayHours]) -> List[DayHours]:
        seen = [d.day for d in days]
        if len(seen) != len(set(seen)):
            raise ValueError("each day may appear only once")
        return days


class CapacityUpdate(BaseModel):
    # null goes back to the default: one customer per active staff member.
    capacity: Optional[int] = Field(default=None, ge=1, le=100)


class HolidayCreate(BaseModel):
    date: date
    note: Optional[str] = Field(default=None, max_length=120)

    @field_validator("note")
    @classmethod
    def blank_is_none(cls, v: Optional[str]) -> Optional[str]:
        return (v.strip() or None) if v is not None else None


class Holiday(BaseModel):
    date: date
    note: Optional[str] = None


class ShopSchedule(BaseModel):
    shop_id: str
    timezone: str
    # False until the owner saves a week: such a shop can be booked at any future time.
    configured: bool
    # Always seven entries, Monday first.
    weekly: List[DayHours]
    # Today and later, soonest first.
    holidays: List[Holiday]
    # How many bookings may overlap at any moment.
    capacity: int
    capacity_override: Optional[int] = None
    active_staff: int
    updated_at: Optional[datetime] = None
    # False while the shop awaits approval or is switched off: booking_service turns bookings away.
    accepting_bookings: bool = True
