from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import RatingExistsError, ShopNotFoundError
from app.database import get_db
from app.dependencies import (
    BookingLookup,
    Caller,
    NameLookup,
    ensure_owner,
    get_booking_lookup,
    get_name_lookup,
    optional_caller,
    require_caller,
)
from app.schemas.shop import ShopCreate, ShopRatingCreate, ShopResponse, ShopUpdate
from app.services.shop_service import shop_service

router = APIRouter()


def for_caller(shop, caller: Optional[Caller]) -> ShopResponse:
    """A shop as this caller may see it: its phone and email only for its owner and admins.

    Customers reach a shop through the platform (booking chat, masked calls), so bookings and the
    commission on them stay on the platform.
    """
    view = ShopResponse.model_validate(shop)
    if caller is not None and (caller.is_admin or caller.user_id == view.owner_id):
        return view
    return view.model_copy(update={"phone": None, "email": None})


@router.post("/shops", response_model=ShopResponse, status_code=201)
async def create_shop(data: ShopCreate, db: AsyncSession = Depends(get_db), caller: Caller = Depends(require_caller)):
    # Only admins may open a shop on someone else's behalf.
    ensure_owner(data.owner_id, caller)
    # An owner runs one shop (the dashboard manages a single shop); a repeat submit must not open a second.
    if not caller.is_admin and await shop_service.list_shops(db, skip=0, limit=1, owner_id=data.owner_id):
        raise HTTPException(status_code=409, detail="You already have a shop")
    return await shop_service.create_shop(db, data)


@router.get("/shops", response_model=List[ShopResponse])
async def list_shops(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    owner_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    caller: Optional[Caller] = Depends(optional_caller),
):
    shops = await shop_service.list_shops(db, skip=skip, limit=limit, owner_id=owner_id)
    return [for_caller(s, caller) for s in shops]


@router.get("/shops/search", response_model=List[ShopResponse])
async def search_shops(
    q: Optional[str] = None,
    city: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    caller: Optional[Caller] = Depends(optional_caller),
):
    shops = await shop_service.search_shops(db, q=q, city=city, category=category, limit=limit)
    return [for_caller(s, caller) for s in shops]


@router.get("/shops/{shop_id}", response_model=ShopResponse)
async def get_shop(
    shop_id: str, db: AsyncSession = Depends(get_db), caller: Optional[Caller] = Depends(optional_caller)
):
    try:
        return for_caller(await shop_service.get_shop(db, shop_id), caller)
    except ShopNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.put("/shops/{shop_id}", response_model=ShopResponse)
async def update_shop(
    shop_id: str,
    data: ShopUpdate,
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(require_caller),
):
    try:
        ensure_owner((await shop_service.get_shop(db, shop_id)).owner_id, caller)
        return await shop_service.update_shop(db, shop_id, data)
    except ShopNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.delete("/shops/{shop_id}", status_code=204)
async def delete_shop(shop_id: str, db: AsyncSession = Depends(get_db), caller: Caller = Depends(require_caller)):
    try:
        ensure_owner((await shop_service.get_shop(db, shop_id)).owner_id, caller)
        await shop_service.delete_shop(db, shop_id)
    except ShopNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/shops/{shop_id}/rating", response_model=ShopResponse)
async def rate_shop(
    shop_id: str,
    data: ShopRatingCreate,
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(require_caller),
    lookup_booking: BookingLookup = Depends(get_booking_lookup),
    lookup_name: NameLookup = Depends(get_name_lookup),
):
    """Customers rate a shop, with an optional written review, once per completed booking with it."""
    booking = await lookup_booking(data.booking_id, caller)
    if booking is None or booking.get("customer_id") != caller.user_id or booking.get("shop_id") != shop_id:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.get("status") != "COMPLETED":
        raise HTTPException(status_code=409, detail="Only completed bookings can be rated")
    try:
        rated = await shop_service.add_rating(
            db,
            shop_id,
            data.booking_id,
            caller.user_id,
            data.rating,
            data.comment,
            service_id=booking.get("service_id"),
            reviewer_name=await lookup_name(caller),
        )
        return for_caller(rated, caller)
    except ShopNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except RatingExistsError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
