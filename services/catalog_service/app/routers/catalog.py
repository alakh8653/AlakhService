from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import structlog
from app.database import get_db
from app.schemas.catalog import (
    ServiceCategoryCreate, ServiceCategoryUpdate, ServiceCategoryResponse,
    ServiceItemCreate, ServiceItemUpdate, ServiceItemResponse, ServiceItemListResponse,
    PricingTierCreate, PricingTierResponse, ServiceMediaCreate, ServiceMediaResponse,
    ServiceVariantCreate, ServiceVariantResponse, SearchCatalogParams,
)
from app.services.catalog_service import catalog_service
from app.core.exceptions import CategoryNotFoundError, ServiceNotFoundError, SlugConflictError
import redis.asyncio as aioredis
from app.config import settings

router = APIRouter()
log = structlog.get_logger()

async def get_redis():
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        yield r
    finally:
        await r.aclose()

@router.get("/catalog/categories", response_model=List[ServiceCategoryResponse])
async def list_categories(parent_id: Optional[str] = Query(None), db: AsyncSession = Depends(get_db)):
    return await catalog_service.list_categories(db, parent_id)

@router.get("/catalog/categories/tree")
async def get_tree(db: AsyncSession = Depends(get_db), redis=Depends(get_redis)):
    return await catalog_service.get_service_tree(db, redis)

@router.post("/catalog/categories", response_model=ServiceCategoryResponse, status_code=201)
async def create_category(payload: ServiceCategoryCreate, db: AsyncSession = Depends(get_db)):
    try:
        return await catalog_service.create_category(db, payload)
    except SlugConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))

@router.get("/catalog/categories/{category_id}", response_model=ServiceCategoryResponse)
async def get_category(category_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await catalog_service.get_category(db, category_id)
    except CategoryNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.put("/catalog/categories/{category_id}", response_model=ServiceCategoryResponse)
async def update_category(category_id: str, payload: ServiceCategoryUpdate, db: AsyncSession = Depends(get_db)):
    try:
        return await catalog_service.update_category(db, category_id, payload)
    except CategoryNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/catalog/categories/{category_id}")
async def delete_category(category_id: str, db: AsyncSession = Depends(get_db)):
    try:
        await catalog_service.delete_category(db, category_id)
        return {"success": True}
    except CategoryNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/catalog/services", response_model=ServiceItemListResponse)
async def list_services(category_id: Optional[str] = Query(None), page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=100), db: AsyncSession = Depends(get_db)):
    return await catalog_service.list_services(db, category_id, page, per_page)

@router.get("/catalog/services/popular", response_model=List[ServiceItemResponse])
async def popular_services(limit: int = Query(10, ge=1, le=50), db: AsyncSession = Depends(get_db), redis=Depends(get_redis)):
    return await catalog_service.get_popular_services(db, redis, limit)

@router.get("/catalog/services/featured", response_model=List[ServiceItemResponse])
async def featured_services(db: AsyncSession = Depends(get_db), redis=Depends(get_redis)):
    return await catalog_service.get_featured_services(db, redis)

@router.post("/catalog/services/search", response_model=ServiceItemListResponse)
async def search_catalog(params: SearchCatalogParams, db: AsyncSession = Depends(get_db)):
    return await catalog_service.search_catalog(db, params.query, params.category_id, params.min_price_cents, params.max_price_cents, params.page, params.per_page)

@router.post("/catalog/services", response_model=ServiceItemResponse, status_code=201)
async def create_service(payload: ServiceItemCreate, db: AsyncSession = Depends(get_db)):
    try:
        return await catalog_service.create_service(db, payload)
    except SlugConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))

@router.get("/catalog/services/{service_id}", response_model=ServiceItemResponse)
async def get_service(service_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await catalog_service.get_service(db, service_id)
    except ServiceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/catalog/services/slug/{slug}", response_model=ServiceItemResponse)
async def get_service_by_slug(slug: str, db: AsyncSession = Depends(get_db)):
    try:
        return await catalog_service.get_service_by_slug(db, slug)
    except ServiceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.put("/catalog/services/{service_id}", response_model=ServiceItemResponse)
async def update_service(service_id: str, payload: ServiceItemUpdate, db: AsyncSession = Depends(get_db)):
    try:
        return await catalog_service.update_service(db, service_id, payload)
    except ServiceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/catalog/services/{service_id}")
async def delete_service(service_id: str, db: AsyncSession = Depends(get_db)):
    try:
        await catalog_service.delete_service(db, service_id)
        return {"success": True}
    except ServiceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/catalog/services/{service_id}/pricing-tiers", response_model=PricingTierResponse, status_code=201)
async def add_pricing_tier(service_id: str, payload: PricingTierCreate, db: AsyncSession = Depends(get_db)):
    return await catalog_service.add_pricing_tier(db, service_id, payload)

@router.post("/catalog/services/{service_id}/media", response_model=ServiceMediaResponse, status_code=201)
async def add_media(service_id: str, payload: ServiceMediaCreate, db: AsyncSession = Depends(get_db)):
    return await catalog_service.add_media(db, service_id, payload)

@router.post("/catalog/services/{service_id}/variants", response_model=ServiceVariantResponse, status_code=201)
async def add_variant(service_id: str, payload: ServiceVariantCreate, db: AsyncSession = Depends(get_db)):
    return await catalog_service.add_variant(db, service_id, payload)
