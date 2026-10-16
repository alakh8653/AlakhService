from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NoProvidersAvailableError
from app.database import get_db
from app.dependencies import (
    BookingAssigner,
    Caller,
    ensure_self_or_admin,
    get_booking_assigner,
    require_admin,
    require_caller,
)
from app.schemas.dispatch import AssignRequest, AssignResponse, AvailableProviderResponse, ProviderLocationUpdate
from app.services.dispatch_service import dispatch_service

router = APIRouter()


# Matching a booking to a provider is a platform operation, not something users trigger.
@router.post("/dispatch/assign", response_model=AssignResponse)
async def assign_dispatch(
    data: AssignRequest,
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(require_admin),
    assign_booking: BookingAssigner = Depends(get_booking_assigner),
):
    """Pick the nearest provider and give them the booking (a platform operation, not a user one)."""
    try:
        result = await dispatch_service.assign(db, data)
    except NoProvidersAvailableError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    # Write the choice back to booking_service; if it refuses, the dispatch job is rolled back with the request.
    await assign_booking(data.booking_id, result.provider_id, caller)
    return result


@router.post("/providers/location", status_code=200)
async def update_provider_location(
    data: ProviderLocationUpdate, db: AsyncSession = Depends(get_db), caller: Caller = Depends(require_caller)
):
    ensure_self_or_admin(data.provider_id, caller)
    return await dispatch_service.update_provider_location(db, data)


# Returns providers' live positions, so it is for dispatch operators only.
@router.get(
    "/providers/available", response_model=List[AvailableProviderResponse], dependencies=[Depends(require_admin)]
)
async def get_available_providers(
    lat: float = Query(...),
    lon: float = Query(...),
    radius_km: float = Query(default=10.0),
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(require_caller),
):
    return await dispatch_service.get_available_providers(db, lat, lon, radius_km)
