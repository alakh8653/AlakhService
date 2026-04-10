import uuid
from datetime import datetime, timezone
from typing import Optional
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.tracking import ProviderLocation, GeofenceRegion
from app.schemas.tracking import LocationUpdate, GeofenceCreate, GeofenceCheckResponse
from app.core.kalman import KalmanGPSFilter
from app.core.geofence import is_in_circular_geofence
from app.core.exceptions import LocationNotFoundError, GeofenceNotFoundError

log = structlog.get_logger()

# Per-provider Kalman filters (in-memory, would use Redis in production)
_kalman_filters: dict[str, KalmanGPSFilter] = {}


class TrackingService:

    def _get_filter(self, provider_id: str) -> KalmanGPSFilter:
        if provider_id not in _kalman_filters:
            _kalman_filters[provider_id] = KalmanGPSFilter()
        return _kalman_filters[provider_id]

    async def update_location(self, db: AsyncSession, data: LocationUpdate) -> ProviderLocation:
        kf = self._get_filter(data.provider_id)
        accuracy = data.accuracy or 1.0
        smooth_lat, smooth_lon = kf.update(data.latitude, data.longitude, accuracy)

        loc = ProviderLocation(
            id=str(uuid.uuid4()),
            provider_id=data.provider_id,
            latitude=smooth_lat,
            longitude=smooth_lon,
            accuracy=data.accuracy,
            speed=data.speed,
            heading=data.heading,
            timestamp=datetime.now(timezone.utc),
        )
        db.add(loc)
        await db.flush()
        log.info("location_updated", provider_id=data.provider_id, lat=smooth_lat, lon=smooth_lon)
        return loc

    async def get_latest_location(self, db: AsyncSession, provider_id: str) -> ProviderLocation:
        result = await db.execute(
            select(ProviderLocation)
            .where(ProviderLocation.provider_id == provider_id)
            .order_by(ProviderLocation.timestamp.desc())
            .limit(1)
        )
        loc = result.scalar_one_or_none()
        if not loc:
            raise LocationNotFoundError()
        return loc

    async def create_geofence(self, db: AsyncSession, data: GeofenceCreate) -> GeofenceRegion:
        gf = GeofenceRegion(
            id=str(uuid.uuid4()),
            name=data.name,
            center_lat=data.center_lat,
            center_lng=data.center_lng,
            radius_meters=data.radius_meters,
            is_active=True,
        )
        db.add(gf)
        await db.flush()
        log.info("geofence_created", geofence_id=gf.id, name=gf.name)
        return gf

    async def check_geofence(self, db: AsyncSession, geofence_id: str, lat: float, lon: float) -> GeofenceCheckResponse:
        result = await db.execute(select(GeofenceRegion).where(GeofenceRegion.id == geofence_id))
        gf = result.scalar_one_or_none()
        if not gf:
            raise GeofenceNotFoundError()
        is_inside = is_in_circular_geofence(lat, lon, gf.center_lat, gf.center_lng, gf.radius_meters)
        return GeofenceCheckResponse(geofence_id=geofence_id, is_inside=is_inside, latitude=lat, longitude=lon)


tracking_service = TrackingService()
