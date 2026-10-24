from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import RatingExistsError, ShopNotFoundError
from app.core.internal import is_internal
from app.core.reporting import Reporter, get_reporter
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
from app.services.shop_service import is_public, shop_service

router = APIRouter()

# Only for the owner and admins: how to reach the shop off-platform, and its KYC and review details.
PRIVATE_FIELDS = ("phone", "email", "legal_name", "legal_address", "gstin", "rejection_reason", "submitted_at")


def can_manage(shop, caller: Optional[Caller]) -> bool:
    return caller is not None and (caller.is_admin or caller.user_id == shop.owner_id)


def for_caller(shop, caller: Optional[Caller]) -> ShopResponse:
    """A shop as this caller may see it: its phone, email and KYC details only for its owner and admins.

    Customers reach a shop through the platform (booking chat, masked calls), so bookings and the
    commission on them stay on the platform.
    """
    view = ShopResponse.model_validate(shop)
    if can_manage(shop, caller):
        return view
    return view.model_copy(update=dict.fromkeys(PRIVATE_FIELDS))


@router.post("/shops", response_model=ShopResponse, status_code=201)
async def create_shop(data: ShopCreate, db: AsyncSession = Depends(get_db), caller: Caller = Depends(require_caller)):
    # Only admins may open a shop on someone else's behalf.
    ensure_owner(data.owner_id, caller)
    # An owner runs one shop (the dashboard manages a single shop); a repeat submit must not open a second.
    if not caller.is_admin and await shop_service.owner_has_shop(db, data.owner_id):
        raise HTTPException(status_code=409, detail="You already have a shop")
    # New shops wait for an admin's review (PENDING_REVIEW) and stay out of the listings until approved.
    return await shop_service.create_shop(db, data)


@router.get("/shops", response_model=List[ShopResponse])
async def list_shops(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    owner_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    caller: Optional[Caller] = Depends(optional_caller),
):
    # An owner listing their own shops (the dashboard) also sees the ones in review, rejected or closed.
    own = owner_id is not None and caller is not None and (caller.is_admin or caller.user_id == owner_id)
    shops = await shop_service.list_shops(db, skip=skip, limit=limit, owner_id=owner_id, include_hidden=own)
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
    shop_id: str,
    db: AsyncSession = Depends(get_db),
    caller: Optional[Caller] = Depends(optional_caller),
    x_internal_key: Optional[str] = Header(None),
):
    try:
        shop = await shop_service.get_shop(db, shop_id)
    except ShopNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    # A shop in review, rejected or closed is not there for customers; its owner and admins still see it,
    # and so do platform services that send the internal key (e.g. to find the owner of a pending shop).
    if not is_public(shop) and not can_manage(shop, caller) and not is_internal(x_internal_key):
        raise HTTPException(status_code=404, detail="Shop not found")
    return for_caller(shop, caller)


# Checked by an admin on approval: once approved, the owner cannot change them alone.
LOCKED_WHEN_APPROVED = ("legal_name", "gstin")


@router.put("/shops/{shop_id}", response_model=ShopResponse)
async def update_shop(
    shop_id: str,
    data: ShopUpdate,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(require_caller),
    reporter: Reporter = Depends(get_reporter),
):
    try:
        shop = await shop_service.get_shop(db, shop_id)
        was_public = is_public(shop)
        ensure_owner(shop.owner_id, caller)
        changes = data.model_dump(exclude_unset=True)
        if not caller.is_admin and shop.verification_status == "APPROVED":
            locked = [f for f in LOCKED_WHEN_APPROVED if f in changes and changes[f] != getattr(shop, f)]
            if locked:
                raise HTTPException(
                    status_code=409,
                    detail="Your verified legal name and GSTIN can only be changed by support. Please contact us.",
                )
        shop = await shop_service.update_shop(db, shop_id, data)
        if is_public(shop) != was_public:  # switched on or off
            background.add_task(reporter.sync_listing, shop.id, is_public(shop))
        return shop
    except ShopNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.delete("/shops/{shop_id}", status_code=204)
async def delete_shop(
    shop_id: str,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(require_caller),
    reporter: Reporter = Depends(get_reporter),
):
    try:
        ensure_owner((await shop_service.get_shop(db, shop_id)).owner_id, caller)
        await shop_service.delete_shop(db, shop_id)
        background.add_task(reporter.sync_listing, shop_id, False)
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
