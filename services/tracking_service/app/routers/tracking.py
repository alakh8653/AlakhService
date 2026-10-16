from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import GeofenceNotFoundError, LocationNotFoundError
from app.database import get_db
from app.dependencies import (
    Caller,
    TrackingCheck,
    ensure_self_or_admin,
    get_tracking_check,
    require_admin,
    require_caller,
)
from app.schemas.tracking import (
    GeofenceCheckResponse,
    GeofenceCreate,
    GeofenceResponse,
    LocationResponse,
    LocationUpdate,
)
from app.services.tracking_service import tracking_service

router = APIRouter()


@router.post("/locations", response_model=LocationResponse, status_code=201)
async def update_location(
    data: LocationUpdate, db: AsyncSession = Depends(get_db), caller: Caller = Depends(require_caller)
):
    # Providers report only their own position.
    ensure_self_or_admin(data.provider_id, caller)
    return await tracking_service.update_location(db, data)


@router.get("/locations/{provider_id}", response_model=LocationResponse)
async def get_location(
    provider_id: str,
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(require_caller),
    tracking_check: TrackingCheck = Depends(get_tracking_check),
):
    # Live positions are shared only with the provider, admins, and whoever they are serving right now.
    if not caller.is_admin and caller.user_id != provider_id and not await tracking_check(provider_id, caller):
        raise HTTPException(status_code=404, detail="Location not found")
    try:
        return await tracking_service.get_latest_location(db, provider_id)
    except LocationNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/geofences", response_model=GeofenceResponse, status_code=201, dependencies=[Depends(require_admin)])
async def create_geofence(data: GeofenceCreate, db: AsyncSession = Depends(get_db)):
    return await tracking_service.create_geofence(db, data)


@router.get("/geofences/{geofence_id}/check", response_model=GeofenceCheckResponse)
async def check_geofence(
    geofence_id: str,
    lat: float = Query(...),
    lon: float = Query(...),
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(require_caller),
):
    try:
        return await tracking_service.check_geofence(db, geofence_id, lat, lon)
    except GeofenceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
