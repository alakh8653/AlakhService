"""Opening hours, holidays and capacity of a shop: anyone may read them, only the owner may change them."""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ShopNotFoundError
from app.database import get_db
from app.dependencies import Caller, ensure_owner, require_caller
from app.schemas.hours import CapacityUpdate, HolidayCreate, ShopSchedule, WeeklyHoursUpdate
from app.services import hours_service
from app.services.shop_service import shop_service

router = APIRouter()

# Far enough for festival closures announced in advance; further out is more likely a typo in the year.
HOLIDAY_HORIZON = timedelta(days=366)


async def _shop(db: AsyncSession, shop_id: str):
    try:
        return await shop_service.get_shop(db, shop_id)
    except ShopNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


async def _owned_shop(db: AsyncSession, shop_id: str, caller: Caller):
    shop = await _shop(db, shop_id)
    ensure_owner(shop.owner_id, caller)
    return shop


@router.get("/shops/{shop_id}/hours", response_model=ShopSchedule)
async def get_hours(shop_id: str, db: AsyncSession = Depends(get_db)):
    """Public: the customer app shows these and booking_service checks bookings against them."""
    await _shop(db, shop_id)
    return await hours_service.get_schedule(db, shop_id)


@router.put("/shops/{shop_id}/hours", response_model=ShopSchedule)
async def set_hours(
    shop_id: str, data: WeeklyHoursUpdate, db: AsyncSession = Depends(get_db), caller: Caller = Depends(require_caller)
):
    await _owned_shop(db, shop_id, caller)
    await hours_service.set_weekly_hours(db, shop_id, data.weekly)
    return await hours_service.get_schedule(db, shop_id)


@router.put("/shops/{shop_id}/capacity", response_model=ShopSchedule)
async def set_capacity(
    shop_id: str, data: CapacityUpdate, db: AsyncSession = Depends(get_db), caller: Caller = Depends(require_caller)
):
    await _owned_shop(db, shop_id, caller)
    await hours_service.set_capacity(db, shop_id, data.capacity)
    return await hours_service.get_schedule(db, shop_id)


@router.post("/shops/{shop_id}/holidays", response_model=ShopSchedule, status_code=201)
async def add_holiday(
    shop_id: str, data: HolidayCreate, db: AsyncSession = Depends(get_db), caller: Caller = Depends(require_caller)
):
    await _owned_shop(db, shop_id, caller)
    today = hours_service.today_in_shop_zone()
    if data.date < today:
        raise HTTPException(status_code=422, detail="That date has already passed")
    if data.date > today + HOLIDAY_HORIZON:
        raise HTTPException(status_code=422, detail="Holidays can be added up to a year ahead")
    try:
        await hours_service.add_holiday(db, shop_id, data.date, data.note)
    except hours_service.HolidayExistsError:
        raise HTTPException(status_code=409, detail=f"{data.date.isoformat()} is already a holiday") from None
    return await hours_service.get_schedule(db, shop_id)


@router.delete("/shops/{shop_id}/holidays/{day}", status_code=204)
async def remove_holiday(
    shop_id: str, day: date, db: AsyncSession = Depends(get_db), caller: Caller = Depends(require_caller)
):
    await _owned_shop(db, shop_id, caller)
    if not await hours_service.remove_holiday(db, shop_id, day):
        raise HTTPException(status_code=404, detail="No holiday on that date")
    return Response(status_code=204)
