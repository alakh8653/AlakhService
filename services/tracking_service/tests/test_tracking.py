import pytest
import pytest_asyncio
import os
import sys

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.database import Base
from app.models.tracking import ProviderLocation, GeofenceRegion
from app.services.tracking_service import TrackingService
from app.schemas.tracking import LocationUpdate, GeofenceCreate
from app.core.kalman import KalmanGPSFilter
from app.core.geofence import is_in_circular_geofence, point_in_polygon
from app.core.exceptions import LocationNotFoundError, GeofenceNotFoundError

pytest_plugins = ("anyio",)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine):
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
def service():
    return TrackingService()


@pytest.mark.anyio
async def test_kalman_filter_smoothing():
    kf = KalmanGPSFilter()
    # First update initializes
    lat1, lon1 = kf.update(28.6139, 77.2090)
    assert lat1 == 28.6139
    assert lon1 == 77.2090
    # Second update should smooth towards noisy reading
    lat2, lon2 = kf.update(28.6200, 77.2150, accuracy=2.0)
    # Smoothed value should be between original and noisy reading
    assert 28.6139 <= lat2 <= 28.6200
    assert 77.2090 <= lon2 <= 77.2150


@pytest.mark.anyio
async def test_kalman_reduces_noise():
    kf = KalmanGPSFilter()
    kf.update(28.6139, 77.2090)
    # Inject a noisy reading far away
    lat, lon = kf.update(28.7000, 77.3000, accuracy=10.0)
    # Should not jump all the way to noisy reading
    assert lat < 28.7000
    assert lon < 77.3000


@pytest.mark.anyio
async def test_geofence_check_inside(db_session, service):
    gf = await service.create_geofence(db_session, GeofenceCreate(
        name="Test Zone", center_lat=28.6139, center_lng=77.2090, radius_meters=1000.0
    ))
    result = await service.check_geofence(db_session, gf.id, 28.6139, 77.2090)
    assert result.is_inside is True


@pytest.mark.anyio
async def test_geofence_check_outside(db_session, service):
    gf = await service.create_geofence(db_session, GeofenceCreate(
        name="Small Zone", center_lat=28.6139, center_lng=77.2090, radius_meters=100.0
    ))
    # Point ~50km away
    result = await service.check_geofence(db_session, gf.id, 28.0000, 77.2090)
    assert result.is_inside is False


@pytest.mark.anyio
async def test_update_location(db_session, service):
    data = LocationUpdate(provider_id="prov-1", latitude=28.6139, longitude=77.2090, accuracy=5.0)
    loc = await service.update_location(db_session, data)
    assert loc.provider_id == "prov-1"
    assert loc.id is not None


@pytest.mark.anyio
async def test_get_latest_location(db_session, service):
    await service.update_location(db_session, LocationUpdate(provider_id="prov-2", latitude=28.0, longitude=77.0))
    await service.update_location(db_session, LocationUpdate(provider_id="prov-2", latitude=28.1, longitude=77.1))
    loc = await service.get_latest_location(db_session, "prov-2")
    assert loc.provider_id == "prov-2"


@pytest.mark.anyio
async def test_location_not_found(db_session, service):
    with pytest.raises(LocationNotFoundError):
        await service.get_latest_location(db_session, "nonexistent-provider")


@pytest.mark.anyio
async def test_point_in_polygon():
    # Square polygon around a point
    polygon = [(0.0, 0.0), (0.0, 1.0), (1.0, 1.0), (1.0, 0.0)]
    assert point_in_polygon(0.5, 0.5, polygon) is True
    assert point_in_polygon(2.0, 2.0, polygon) is False
