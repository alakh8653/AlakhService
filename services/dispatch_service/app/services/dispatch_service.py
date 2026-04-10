import uuid
from datetime import datetime, timezone, timedelta
from typing import List
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.dispatch import DispatchJob, AvailableProvider
from app.schemas.dispatch import AssignRequest, AssignResponse, ProviderLocationUpdate
from app.core.hungarian import haversine_distance, hungarian_algorithm
from app.core.exceptions import NoProvidersAvailableError

log = structlog.get_logger()


class DispatchService:

    async def assign(self, db: AsyncSession, data: AssignRequest) -> AssignResponse:
        if not data.providers:
            raise NoProvidersAvailableError()

        # Build cost matrix: 1 booking x N providers
        costs = [[haversine_distance(data.booking_lat, data.booking_lon, p.latitude, p.longitude) for p in data.providers]]
        assignments = hungarian_algorithm(costs)

        if not assignments:
            raise NoProvidersAvailableError()

        row, col = assignments[0]
        best_provider = data.providers[col]
        distance = costs[0][col]

        job = DispatchJob(
            id=str(uuid.uuid4()),
            booking_id=data.booking_id,
            provider_id=best_provider.provider_id,
            status="ASSIGNED",
            distance_km=distance,
            assigned_at=datetime.now(timezone.utc),
            estimated_arrival_at=datetime.now(timezone.utc) + timedelta(minutes=int(distance * 3)),
        )
        db.add(job)
        await db.flush()
        log.info("dispatch_assigned", booking_id=data.booking_id, provider_id=best_provider.provider_id, distance_km=distance)

        return AssignResponse(
            booking_id=data.booking_id,
            provider_id=best_provider.provider_id,
            distance_km=distance,
            job_id=job.id,
        )

    async def update_provider_location(self, db: AsyncSession, data: ProviderLocationUpdate) -> dict:
        result = await db.execute(select(AvailableProvider).where(AvailableProvider.provider_id == data.provider_id))
        provider = result.scalar_one_or_none()
        if provider:
            provider.latitude = data.latitude
            provider.longitude = data.longitude
            provider.is_available = data.is_available
            provider.last_update = datetime.now(timezone.utc)
        else:
            provider = AvailableProvider(
                id=str(uuid.uuid4()),
                provider_id=data.provider_id,
                latitude=data.latitude,
                longitude=data.longitude,
                is_available=data.is_available,
                last_update=datetime.now(timezone.utc),
            )
            db.add(provider)
        await db.flush()
        return {"status": "updated", "provider_id": data.provider_id}

    async def get_available_providers(self, db: AsyncSession, lat: float, lon: float, radius_km: float) -> List[AvailableProvider]:
        result = await db.execute(select(AvailableProvider).where(AvailableProvider.is_available == True))
        all_providers = list(result.scalars().all())
        nearby = [
            p for p in all_providers
            if haversine_distance(lat, lon, p.latitude, p.longitude) <= radius_km
        ]
        return nearby


dispatch_service = DispatchService()
