from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NoProvidersAvailableError
from app.database import get_db
from app.dependencies import Caller, ensure_self_or_admin, require_admin, require_caller
from app.schemas.dispatch import AssignRequest, AssignResponse, AvailableProviderResponse, ProviderLocationUpdate
from app.services.dispatch_service import dispatch_service

router = APIRouter()


# Matching a booking to a provider is a platform operation, not something users trigger.
@router.post("/dispatch/assign", response_model=AssignResponse, dependencies=[Depends(require_admin)])
async def assign_dispatch(data: AssignRequest, db: AsyncSession = Depends(get_db)):
    try:
        return await dispatch_service.assign(db, data)
    except NoProvidersAvailableError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/providers/location", status_code=200)
async def update_provider_location(
    data: ProviderLocationUpdate, db: AsyncSession = Depends(get_db), caller: Caller = Depends(require_caller)
):
    ensure_self_or_admin(data.provider_id, caller)
    return await dispatch_service.update_provider_location(db, data)


@router.get("/providers/available", response_model=List[AvailableProviderResponse])
async def get_available_providers(
    lat: float = Query(...),
    lon: float = Query(...),
    radius_km: float = Query(default=10.0),
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(require_caller),
):
    return await dispatch_service.get_available_providers(db, lat, lon, radius_km)
