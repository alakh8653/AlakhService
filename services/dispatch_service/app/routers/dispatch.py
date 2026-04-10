from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.database import get_db
from app.schemas.dispatch import AssignRequest, AssignResponse, ProviderLocationUpdate, AvailableProviderResponse
from app.services.dispatch_service import dispatch_service
from app.core.exceptions import NoProvidersAvailableError

router = APIRouter()


@router.post("/dispatch/assign", response_model=AssignResponse)
async def assign_dispatch(data: AssignRequest, db: AsyncSession = Depends(get_db)):
    try:
        return await dispatch_service.assign(db, data)
    except NoProvidersAvailableError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/providers/location", status_code=200)
async def update_provider_location(data: ProviderLocationUpdate, db: AsyncSession = Depends(get_db)):
    return await dispatch_service.update_provider_location(db, data)


@router.get("/providers/available", response_model=List[AvailableProviderResponse])
async def get_available_providers(
    lat: float = Query(...),
    lon: float = Query(...),
    radius_km: float = Query(default=10.0),
    db: AsyncSession = Depends(get_db),
):
    return await dispatch_service.get_available_providers(db, lat, lon, radius_km)
