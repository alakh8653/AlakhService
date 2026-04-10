import pytest
import pytest_asyncio
import os
import sys
import math

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.database import Base
from app.services.dispatch_service import DispatchService
from app.schemas.dispatch import AssignRequest, ProviderInfo, ProviderLocationUpdate
from app.core.hungarian import haversine_distance, hungarian_algorithm
from app.core.exceptions import NoProvidersAvailableError

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
    return DispatchService()


@pytest.mark.anyio
async def test_haversine_distance():
    # Mumbai to Delhi ~1150 km
    d = haversine_distance(19.0760, 72.8777, 28.6139, 77.2090)
    assert 1100 <= d <= 1200


@pytest.mark.anyio
async def test_haversine_same_point():
    d = haversine_distance(28.6139, 77.2090, 28.6139, 77.2090)
    assert d < 0.001


@pytest.mark.anyio
async def test_hungarian_algorithm_3x3():
    cost_matrix = [
        [4.0, 1.0, 3.0],
        [2.0, 0.0, 5.0],
        [3.0, 2.0, 2.0],
    ]
    assignments = hungarian_algorithm(cost_matrix)
    assert len(assignments) == 3
    rows = [a[0] for a in assignments]
    cols = [a[1] for a in assignments]
    assert len(set(rows)) == 3
    assert len(set(cols)) == 3
    total_cost = sum(cost_matrix[r][c] for r, c in assignments)
    # Optimal assignment should be row0->col1(1), row1->col0(2), row2->col2(2) = 5
    assert total_cost <= 6.0


@pytest.mark.anyio
async def test_hungarian_algorithm_1x1():
    assignments = hungarian_algorithm([[5.0]])
    assert assignments == [(0, 0)]


@pytest.mark.anyio
async def test_dispatch_assign_best_provider(db_session, service):
    providers = [
        ProviderInfo(provider_id="p1", latitude=28.6200, longitude=77.2100),  # close
        ProviderInfo(provider_id="p2", latitude=28.7000, longitude=77.3000),  # far
        ProviderInfo(provider_id="p3", latitude=28.6150, longitude=77.2050),  # closest
    ]
    req = AssignRequest(booking_id="b1", booking_lat=28.6139, booking_lon=77.2090, providers=providers)
    result = await service.assign(db_session, req)
    assert result.provider_id == "p3"
    assert result.distance_km < 1.0


@pytest.mark.anyio
async def test_dispatch_no_providers(db_session, service):
    req = AssignRequest(booking_id="b1", booking_lat=28.6139, booking_lon=77.2090, providers=[])
    with pytest.raises(NoProvidersAvailableError):
        await service.assign(db_session, req)


@pytest.mark.anyio
async def test_update_provider_location(db_session, service):
    await service.update_provider_location(db_session, ProviderLocationUpdate(provider_id="p1", latitude=28.6, longitude=77.2))
    providers = await service.get_available_providers(db_session, 28.6, 77.2, radius_km=50.0)
    assert any(p.provider_id == "p1" for p in providers)
