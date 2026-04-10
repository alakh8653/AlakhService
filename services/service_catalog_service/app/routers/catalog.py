from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.database import get_db
from app.schemas.catalog import CategoryCreate, CategoryResponse, ServiceListingCreate, ServiceListingUpdate, ServiceListingResponse
from app.services.catalog_service import catalog_service
from app.core.exceptions import ServiceListingNotFoundError, CategoryNotFoundError

router = APIRouter()


@router.get("/categories", response_model=List[CategoryResponse])
async def list_categories(db: AsyncSession = Depends(get_db)):
    return await catalog_service.list_categories(db)


@router.post("/categories", response_model=CategoryResponse, status_code=201)
async def create_category(data: CategoryCreate, db: AsyncSession = Depends(get_db)):
    return await catalog_service.create_category(db, data)


@router.get("/services", response_model=List[ServiceListingResponse])
async def list_services(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    return await catalog_service.list_services(db, skip=skip, limit=limit)


@router.post("/services", response_model=ServiceListingResponse, status_code=201)
async def create_service(data: ServiceListingCreate, db: AsyncSession = Depends(get_db)):
    return await catalog_service.create_service(db, data)


@router.get("/services/search", response_model=List[ServiceListingResponse])
async def search_services(
    q: Optional[str] = None,
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    return await catalog_service.search_services(db, q=q, category=category)


@router.get("/services/{service_id}", response_model=ServiceListingResponse)
async def get_service(service_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await catalog_service.get_service(db, service_id)
    except ServiceListingNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/services/{service_id}", response_model=ServiceListingResponse)
async def update_service(service_id: str, data: ServiceListingUpdate, db: AsyncSession = Depends(get_db)):
    try:
        return await catalog_service.update_service(db, service_id, data)
    except ServiceListingNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
