"""Bookable start times of a service on a day, for the customer app's time picker (public)."""

from datetime import date, datetime, timedelta
from typing import Awaitable, Callable, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import availability
from app.database import get_db
from app.dependencies import ScheduleLookup, get_clock, get_schedule_lookup, get_service_lookup
from app.services.booking_service import booking_service

router = APIRouter()

# Used when a listing has no duration (the customer then gives one when booking).
DEFAULT_DURATION_MINUTES = 30


class OpenInterval(BaseModel):
    start: str
    end: str


class AvailableSlot(BaseModel):
    start: datetime  # UTC; send it back as scheduled_at
    time: str  # shop-local "HH:MM", for display
    remaining: int  # places still free at that time


class AvailabilityResponse(BaseModel):
    service_id: str
    shop_id: Optional[str] = None
    date: date
    timezone: str
    # False: the shop has not published opening hours; any future time can be requested (status
    # NOT_CONFIGURED, no slots), so the app offers its own times.
    hours_configured: bool
    # AVAILABLE, CLOSED, HOLIDAY, FULLY_BOOKED, NO_MORE_TODAY or NOT_CONFIGURED.
    status: str
    # Why there are no slots, ready to show ("Closed on this day").
    message: Optional[str] = None
    holiday_note: Optional[str] = None
    duration_minutes: int
    step_minutes: int
    lead_time_minutes: int
    capacity: Optional[int] = None
    open_intervals: List[OpenInterval]
    slots: List[AvailableSlot]


@router.get("/availability", response_model=AvailabilityResponse)
async def get_availability(
    service_id: str = Query(..., min_length=1, max_length=128),
    day: date = Query(..., alias="date", description="YYYY-MM-DD, in the shop's time zone"),
    db: AsyncSession = Depends(get_db),
    lookup_service: Callable[[str], Awaitable[Optional[dict]]] = Depends(get_service_lookup),
    lookup_schedule: ScheduleLookup = Depends(get_schedule_lookup),
    clock: Callable[[], datetime] = Depends(get_clock),
):
    listing = await lookup_service(service_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="Service not found")
    if not listing.get("is_active", False):
        raise HTTPException(status_code=409, detail="Service is not currently offered")
    shop_id = listing.get("shop_id")
    schedule = availability.Schedule.from_shop_service(await lookup_schedule(shop_id) if shop_id else None)
    now = clock()
    today = schedule.local(now).date()
    if day < today:
        raise HTTPException(status_code=422, detail="That date has passed")
    if day > today + timedelta(days=availability.MAX_DAYS_AHEAD):
        raise HTTPException(status_code=422, detail=f"Times can be seen up to {availability.MAX_DAYS_AHEAD} days ahead")
    duration = listing.get("duration_minutes") or DEFAULT_DURATION_MINUTES
    booked = []
    if schedule.configured:
        window_start, window_end = schedule.day_window(day)
        booked = await booking_service.shop_spans(db, shop_id, window_start, window_end + timedelta(minutes=duration))
    result = availability.day_availability(schedule, day, duration, now, booked)
    return AvailabilityResponse(
        service_id=service_id,
        shop_id=shop_id,
        date=day,
        timezone=schedule.timezone,
        hours_configured=schedule.configured,
        status=result.status,
        message=result.message,
        holiday_note=result.holiday_note,
        duration_minutes=duration,
        step_minutes=availability.step_minutes(duration),
        lead_time_minutes=int(availability.LEAD_TIME.total_seconds() // 60),
        capacity=schedule.capacity if schedule.configured else None,
        open_intervals=[
            OpenInterval(start=availability.hhmm(s), end=availability.hhmm(e)) for s, e in result.intervals
        ],
        slots=[AvailableSlot(start=s.start, time=s.time, remaining=s.remaining) for s in result.slots],
    )
