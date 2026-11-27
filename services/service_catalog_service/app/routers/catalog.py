from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.discovery import MODES, SORTS, Discovery
from app.core.exceptions import ServiceListingNotFoundError
from app.database import get_db
from app.dependencies import (
    Caller,
    ListedLookup,
    OwnerLookup,
    TypesLookup,
    ensure_shop_owner,
    get_shop_listed_lookup,
    get_shop_owner_lookup,
    get_shop_types_lookup,
    require_admin,
    require_caller,
    require_internal,
)
from app.schemas.catalog import (
    CategoryCreate,
    CategoryResponse,
    ServiceListingCreate,
    ServiceListingResponse,
    ServiceListingUpdate,
)
from app.services.catalog_service import catalog_service

router = APIRouter()


def discovery_params(
    min_price: Optional[float] = Query(None, ge=0, description="Rupees"),
    max_price: Optional[float] = Query(None, ge=0, description="Rupees"),
    min_rating: Optional[float] = Query(None, ge=1, le=5),
    mode: Optional[str] = Query(None, description="AT_SHOP, AT_HOME or PICKUP_DROP"),
    lat: Optional[float] = Query(None, ge=-90, le=90),
    lng: Optional[float] = Query(None, ge=-180, le=180),
    max_km: Optional[float] = Query(None, gt=0, le=500),
    sort: str = Query("relevance", description="relevance, price_asc, price_desc, rating or distance"),
) -> Discovery:
    """Filters and sort order customers can ask for when browsing or searching."""
    if sort not in SORTS:
        raise HTTPException(status_code=422, detail=f"sort must be one of {', '.join(SORTS)}")
    if mode is not None and mode not in MODES:
        raise HTTPException(status_code=422, detail=f"mode must be one of {', '.join(MODES)}")
    if (lat is None) != (lng is None):
        raise HTTPException(status_code=422, detail="Give both lat and lng, or neither")
    if (sort == "distance" or max_km is not None) and lat is None:
        raise HTTPException(status_code=422, detail="Sorting or limiting by distance needs lat and lng")
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(status_code=422, detail="min_price is above max_price")
    cents = lambda rupees: None if rupees is None else int(round(rupees * 100))  # noqa: E731
    return Discovery(
        min_price_cents=cents(min_price),
        max_price_cents=cents(max_price),
        min_rating=min_rating,
        mode=mode,
        lat=lat,
        lng=lng,
        max_km=max_km,
        sort=sort,
    )


def _ensure_shop_does(service_type: Optional[str], shop_types: List[str]) -> None:
    """A service only goes under a type the shop chose, and so has shown the documents for."""
    if service_type is None or service_type in shop_types:
        return
    if not shop_types:
        raise HTTPException(status_code=503, detail="Shop service unavailable")
    raise HTTPException(status_code=422, detail="Add this type of work to your shop first")


@router.get("/categories", response_model=List[CategoryResponse])
async def list_categories(db: AsyncSession = Depends(get_db, scope="function")):
    return await catalog_service.list_categories(db)


@router.post("/categories", response_model=CategoryResponse, status_code=201, dependencies=[Depends(require_admin)])
async def create_category(data: CategoryCreate, db: AsyncSession = Depends(get_db, scope="function")):
    return await catalog_service.create_category(db, data)


@router.get("/services", response_model=List[ServiceListingResponse])
async def list_services(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
    shop_id: Optional[str] = None,
    include_inactive: bool = False,
    category: Optional[str] = None,
    d: Discovery = Depends(discovery_params),
    db: AsyncSession = Depends(get_db, scope="function"),
):
    return await catalog_service.list_services(
        db, skip=skip, limit=limit, shop_id=shop_id, include_inactive=include_inactive, category=category, d=d
    )


@router.post("/services", response_model=ServiceListingResponse, status_code=201)
async def create_service(
    data: ServiceListingCreate,
    db: AsyncSession = Depends(get_db, scope="function"),
    caller: Caller = Depends(require_caller),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
    lookup_listed: ListedLookup = Depends(get_shop_listed_lookup),
    lookup_types: TypesLookup = Depends(get_shop_types_lookup),
):
    await ensure_shop_owner(data.shop_id, caller, lookup_owner)
    shop_types = await lookup_types(data.shop_id)
    _ensure_shop_does(data.service_type, shop_types)
    return await catalog_service.create_service(
        db,
        data,
        shop_listed=await lookup_listed(data.shop_id),
        shop_category=shop_types[0] if shop_types else None,
    )


@router.get("/services/search", response_model=List[ServiceListingResponse])
async def search_services(
    q: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    d: Discovery = Depends(discovery_params),
    db: AsyncSession = Depends(get_db, scope="function"),
):
    return await catalog_service.search_services(db, q=q, category=category, limit=limit, d=d)


@router.get("/services/{service_id}", response_model=ServiceListingResponse)
async def get_service(service_id: str, db: AsyncSession = Depends(get_db, scope="function")):
    try:
        return await catalog_service.get_service(db, service_id)
    except ServiceListingNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.put("/services/{service_id}", response_model=ServiceListingResponse)
async def update_service(
    service_id: str,
    data: ServiceListingUpdate,
    db: AsyncSession = Depends(get_db, scope="function"),
    caller: Caller = Depends(require_caller),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
    lookup_types: TypesLookup = Depends(get_shop_types_lookup),
):
    try:
        listing = await catalog_service.get_service(db, service_id)
        await ensure_shop_owner(listing.shop_id, caller, lookup_owner)
        if data.service_type is not None:
            _ensure_shop_does(data.service_type, await lookup_types(listing.shop_id))
        return await catalog_service.update_service(db, service_id, data)
    except ServiceListingNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


class ShopFacts(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    rating: Optional[float] = None
    rating_count: Optional[int] = None


class ShopListing(BaseModel):
    listed: bool
    category: Optional[str] = None
    # Where the shop is and how it is rated (older shop_service versions leave it out).
    facts: Optional[ShopFacts] = None
    # Sent with the category; services under a type the shop no longer has go back under its main type.
    extra_categories: Optional[List[str]] = None


internal_router = APIRouter(dependencies=[Depends(require_internal)])


@internal_router.post("/internal/shops/{shop_id}/listing")
async def set_shop_listing(shop_id: str, data: ShopListing, db: AsyncSession = Depends(get_db, scope="function")):
    """shop_service: the shop was approved, rejected, or switched on or off, or changed its type of work."""
    if data.category:
        await catalog_service.set_shop_category(db, shop_id, data.category, data.extra_categories)
    if data.facts is not None:
        f = data.facts
        await catalog_service.set_shop_facts(db, shop_id, f.latitude, f.longitude, f.rating, f.rating_count)
    return {
        "shop_id": shop_id,
        "listed": data.listed,
        "changed": await catalog_service.set_shop_listed(db, shop_id, data.listed),
    }
