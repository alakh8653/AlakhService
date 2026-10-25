from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ServiceListingNotFoundError
from app.database import get_db
from app.dependencies import (
    Caller,
    ListedLookup,
    OwnerLookup,
    ensure_shop_owner,
    get_shop_listed_lookup,
    get_shop_owner_lookup,
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


@router.get("/categories", response_model=List[CategoryResponse])
async def list_categories(db: AsyncSession = Depends(get_db)):
    return await catalog_service.list_categories(db)


@router.post("/categories", response_model=CategoryResponse, status_code=201, dependencies=[Depends(require_admin)])
async def create_category(data: CategoryCreate, db: AsyncSession = Depends(get_db)):
    return await catalog_service.create_category(db, data)


@router.get("/services", response_model=List[ServiceListingResponse])
async def list_services(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
    shop_id: Optional[str] = None,
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
):
    return await catalog_service.list_services(
        db, skip=skip, limit=limit, shop_id=shop_id, include_inactive=include_inactive
    )


@router.post("/services", response_model=ServiceListingResponse, status_code=201)
async def create_service(
    data: ServiceListingCreate,
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(require_caller),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
    lookup_listed: ListedLookup = Depends(get_shop_listed_lookup),
):
    await ensure_shop_owner(data.shop_id, caller, lookup_owner)
    return await catalog_service.create_service(db, data, shop_listed=await lookup_listed(data.shop_id))


@router.get("/services/search", response_model=List[ServiceListingResponse])
async def search_services(
    q: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await catalog_service.search_services(db, q=q, category=category, limit=limit)


@router.get("/services/{service_id}", response_model=ServiceListingResponse)
async def get_service(service_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await catalog_service.get_service(db, service_id)
    except ServiceListingNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.put("/services/{service_id}", response_model=ServiceListingResponse)
async def update_service(
    service_id: str,
    data: ServiceListingUpdate,
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(require_caller),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
):
    try:
        listing = await catalog_service.get_service(db, service_id)
        await ensure_shop_owner(listing.shop_id, caller, lookup_owner)
        return await catalog_service.update_service(db, service_id, data)
    except ServiceListingNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


class ShopListing(BaseModel):
    listed: bool


internal_router = APIRouter(dependencies=[Depends(require_internal)])


@internal_router.post("/internal/shops/{shop_id}/listing")
async def set_shop_listing(shop_id: str, data: ShopListing, db: AsyncSession = Depends(get_db)):
    """shop_service: the shop was approved, rejected, or switched on or off."""
    return {
        "shop_id": shop_id,
        "listed": data.listed,
        "changed": await catalog_service.set_shop_listed(db, shop_id, data.listed),
    }
