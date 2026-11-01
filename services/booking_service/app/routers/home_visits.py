"""Home visits: when the professional reaches the customer's door, and the professional's route for today.

GET /bookings/{id}/arrival   the customer (or the shop, or the professional): planned, on the way, arrived,
                             with the expected arrival and its range.
GET /bookings/assigned/route the professional: today's home visits in order, when to set off for each and
                             the drive, so they can keep to time.
"""

from datetime import datetime
from typing import Callable, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core import home_visits
from app.core.access import OwnerLookup
from app.core.fsm import AT_HOME, BookingStatus
from app.core.names import NameLookup, get_name_lookup
from app.database import get_db
from app.dependencies import get_clock, get_current_user, get_location_lookup, get_shop_owner_lookup
from app.routers.bookings import _visible_booking

router = APIRouter()

NOT_HOME_VISIT, NOT_ASSIGNED, NOT_TODAY, DONE = "NOT_HOME_VISIT", "NOT_ASSIGNED", "NOT_TODAY", "DONE"


class ArrivalStatus(BaseModel):
    booking_id: str
    # PLANNED, ON_THE_WAY, ARRIVED; or NOT_HOME_VISIT, NOT_ASSIGNED (no professional yet), NOT_TODAY, DONE.
    state: str
    scheduled_at: datetime
    arrive_at: Optional[datetime] = None
    arrive_min: Optional[datetime] = None
    arrive_max: Optional[datetime] = None
    travel_minutes: Optional[int] = None
    # Other home visits before this one on the professional's route today.
    jobs_before: Optional[int] = None
    late_minutes: Optional[int] = None


class RouteStop(BaseModel):
    booking_id: str
    booking_number: str
    customer_display_name: str
    state: str
    scheduled_at: datetime
    arrive_at: datetime
    leave_at: datetime
    finish_at: datetime
    travel_minutes: int
    late_minutes: int


def today(now: datetime):
    return home_visits.day_window(now, settings.DISPLAY_TIMEZONE)


async def arrival_for(db, booking, now: datetime, lookup_location) -> ArrivalStatus:
    base = {"booking_id": booking.id, "scheduled_at": booking.scheduled_at}
    if booking.service_mode != AT_HOME:
        return ArrivalStatus(state=NOT_HOME_VISIT, **base)
    if booking.status in (BookingStatus.COMPLETED.value, BookingStatus.CANCELLED.value, BookingStatus.REFUNDED.value):
        return ArrivalStatus(state=DONE, **base)
    if not booking.provider_id or booking.status not in home_visits.ON_ROUTE:
        return ArrivalStatus(state=NOT_ASSIGNED, **base)
    day = today(now)
    if not day[0] <= home_visits._utc(booking.scheduled_at) < day[1]:
        return ArrivalStatus(state=NOT_TODAY, **base)
    _, route = await home_visits.route_for(db, booking.provider_id, day, now, lookup_location)
    a = route.get(booking.id)
    if a is None:
        return ArrivalStatus(state=NOT_ASSIGNED, **base)
    return ArrivalStatus(
        state=a.state,
        arrive_at=a.arrive_at,
        arrive_min=a.arrive_min,
        arrive_max=a.arrive_max,
        travel_minutes=a.travel_minutes,
        jobs_before=a.jobs_before,
        late_minutes=a.late_minutes,
        **base,
    )


@router.get("/bookings/assigned/route", response_model=List[RouteStop])
async def my_route(
    db: AsyncSession = Depends(get_db, scope="function"),
    current_user: dict = Depends(get_current_user),
    lookup_location=Depends(get_location_lookup),
    lookup_names: NameLookup = Depends(get_name_lookup),
    clock: Callable[[], datetime] = Depends(get_clock),
):
    """The professional's home visits today in order: when to leave, the drive, when they arrive."""
    now = home_visits._utc(clock())
    bookings, route = await home_visits.route_for(db, current_user.get("sub"), today(now), now, lookup_location)
    names = await lookup_names([b.customer_id for b in bookings]) if bookings else {}
    by_id = {b.id: b for b in bookings}
    stops = sorted(route.values(), key=lambda a: a.jobs_before)
    return [
        RouteStop(
            booking_id=a.booking_id,
            booking_number=by_id[a.booking_id].booking_number,
            customer_display_name=names.get(by_id[a.booking_id].customer_id) or "Customer",
            state=a.state,
            scheduled_at=by_id[a.booking_id].scheduled_at,
            arrive_at=a.arrive_at,
            leave_at=a.leave_at,
            finish_at=a.finish_at,
            travel_minutes=a.travel_minutes,
            late_minutes=a.late_minutes,
        )
        for a in stops
    ]


@router.get("/bookings/{booking_id}/arrival", response_model=ArrivalStatus)
async def booking_arrival(
    booking_id: str,
    db: AsyncSession = Depends(get_db, scope="function"),
    current_user: dict = Depends(get_current_user),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
    lookup_location=Depends(get_location_lookup),
    clock: Callable[[], datetime] = Depends(get_clock),
):
    """When the professional reaches the customer's door for this home visit."""
    booking, _ = await _visible_booking(db, booking_id, current_user, lookup_owner)
    return await arrival_for(db, booking, home_visits._utc(clock()), lookup_location)
