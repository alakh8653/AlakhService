import pytest
import pytest_asyncio
import os
import sys

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.database import Base
from app.services.analytics_service import AnalyticsService
from app.schemas.analytics import EventBatchCreate, EventCreate, FunnelAnalysisRequest

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
    return AnalyticsService()


@pytest.mark.anyio
async def test_event_ingestion(db_session, service):
    batch = EventBatchCreate(events=[
        EventCreate(event_type="page_view", user_id="u1", session_id="s1"),
        EventCreate(event_type="click", user_id="u1", session_id="s1"),
        EventCreate(event_type="purchase", user_id="u2", session_id="s2"),
    ])
    events = await service.ingest_events(db_session, batch)
    assert len(events) == 3
    assert events[0].event_type == "page_view"
    assert events[2].user_id == "u2"


@pytest.mark.anyio
async def test_funnel_analysis(db_session, service):
    # Insert events for funnel
    batch = EventBatchCreate(events=[
        EventCreate(event_type="visit", user_id="u1"),
        EventCreate(event_type="visit", user_id="u2"),
        EventCreate(event_type="visit", user_id="u3"),
        EventCreate(event_type="signup", user_id="u1"),
        EventCreate(event_type="signup", user_id="u2"),
        EventCreate(event_type="purchase", user_id="u1"),
    ])
    await service.ingest_events(db_session, batch)

    request = FunnelAnalysisRequest(steps=["visit", "signup", "purchase"])
    result = await service.analyze_funnel(db_session, request)
    assert len(result.steps) == 3
    assert result.steps[0].event_type == "visit"
    assert result.steps[0].count == 3
    assert result.steps[1].count == 2
    assert result.steps[2].count == 1
    assert len(result.conversion_rates) == 2
    assert abs(result.conversion_rates[0] - 2/3) < 0.01


@pytest.mark.anyio
async def test_metric_aggregation(db_session, service):
    m = await service.record_metric(db_session, "active_users", 150.0, dimension="daily")
    assert m.metric_name == "active_users"
    assert m.value == 150.0
    assert m.dimension == "daily"


@pytest.mark.anyio
async def test_get_metrics_filtered(db_session, service):
    await service.record_metric(db_session, "revenue", 10000.0)
    await service.record_metric(db_session, "signups", 50.0)
    metrics = await service.get_metrics(db_session, name="revenue")
    assert all(m.metric_name == "revenue" for m in metrics)
    assert len(metrics) >= 1
