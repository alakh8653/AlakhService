"""Events are recorded as the caller; reports are admin-only."""

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models.analytics  # noqa: F401  (registers the models on Base.metadata)
from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models.analytics import AnalyticsEvent


def auth(sub: str, role: str = "user", token_type: str = "access") -> dict:
    token = jwt.encode(
        {"sub": sub, "role": role, "type": token_type}, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return {"Authorization": f"Bearer {token}"}


ALICE, BOB, ADMIN = auth("alice"), auth("bob"), auth("ops", "admin")


@pytest_asyncio.fixture
async def client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            yield session
            await session.commit()

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        ac.factory = factory
        yield ac
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_events_are_recorded_as_the_caller(client):
    batch = {"events": [{"event_type": "page_view", "user_id": "bob"}]}
    assert (await client.post("/api/v1/events", json=batch)).status_code == 401
    assert (
        await client.post("/api/v1/events", json=batch, headers=auth("alice", token_type="refresh"))
    ).status_code == 401
    recorded = await client.post("/api/v1/events", json=batch, headers=ALICE)
    assert recorded.status_code == 201
    assert recorded.json()[0]["user_id"] == "alice"
    backfill = await client.post("/api/v1/events", json=batch, headers=ADMIN)
    assert backfill.json()[0]["user_id"] == "bob"


@pytest.mark.asyncio
async def test_reports_are_admin_only(client):
    for method, url, kwargs in (
        ("get", "/api/v1/metrics", {}),
        ("get", "/api/v1/cohorts", {}),
        ("post", "/api/v1/funnels/analyze", {"json": {"steps": ["a", "b"]}}),
    ):
        assert (await getattr(client, method)(url, headers=ALICE, **kwargs)).status_code == 403
    assert (await client.get("/api/v1/metrics", headers=ADMIN)).status_code == 200


@pytest.mark.asyncio
async def test_event_batches_are_capped(client):
    one = {"event_type": "page_view"}
    assert (await client.post("/api/v1/events", json={"events": [one] * 100}, headers=ALICE)).status_code == 201
    assert (await client.post("/api/v1/events", json={"events": [one] * 101}, headers=ALICE)).status_code == 422


@pytest.mark.asyncio
async def test_cohorts_count_each_user_once_and_retention_by_week(client):
    signup = datetime(2026, 9, 7, 10, tzinfo=timezone.utc)  # a Monday

    def at(user_id, event_type, days):
        return AnalyticsEvent(event_type=event_type, user_id=user_id, created_at=signup + timedelta(days=days))

    async with client.factory() as db:
        db.add_all(
            [
                # alice signs up three times (only the first counts) and is active in week 1 only.
                at("alice", "signup", 0),
                at("alice", "signup", 1),
                at("alice", "signup", 15),
                at("alice", "active", 8),
                # bob is active on signup day (not retention) and in week 2.
                at("bob", "signup", 0),
                at("bob", "active", 0),
                at("bob", "active", 14),
                # carol comes back only after week 2.
                at("carol", "signup", 2),
                at("carol", "active", 23),
                # dave is active but never signed up.
                at("dave", "active", 8),
            ]
        )
        await db.commit()

    cohorts = (await client.get("/api/v1/cohorts", headers=ADMIN)).json()
    assert cohorts == [{"cohort_week": "2026-W36", "user_count": 3, "retained_week1": 1, "retained_week2": 1}]
