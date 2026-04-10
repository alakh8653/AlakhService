from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.tracking import LocationUpdate, LocationResponse, GeofenceCreate, GeofenceResponse, GeofenceCheckResponse
from app.services.tracking_service import tracking_service
from app.core.exceptions import LocationNotFoundError, GeofenceNotFoundError

router = APIRouter()


@router.post("/locations", response_model=LocationResponse, status_code=201)
async def update_location(data: LocationUpdate, db: AsyncSession = Depends(get_db)):
    return await tracking_service.update_location(db, data)


@router.get("/locations/{provider_id}", response_model=LocationResponse)
async def get_location(provider_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await tracking_service.get_latest_location(db, provider_id)
    except LocationNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/geofences", response_model=GeofenceResponse, status_code=201)
async def create_geofence(data: GeofenceCreate, db: AsyncSession = Depends(get_db)):
    return await tracking_service.create_geofence(db, data)


@router.get("/geofences/{geofence_id}/check", response_model=GeofenceCheckResponse)
async def check_geofence(
    geofence_id: str,
    lat: float = Query(...),
    lon: float = Query(...),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await tracking_service.check_geofence(db, geofence_id, lat, lon)
    except GeofenceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
