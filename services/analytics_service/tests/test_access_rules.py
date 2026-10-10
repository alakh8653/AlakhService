"""Events are recorded as the caller; reports are admin-only."""
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


def auth(sub: str, role: str = "user", token_type: str = "access") -> dict:
    token = jwt.encode({"sub": sub, "role": role, "type": token_type}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
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
        yield ac
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_events_are_recorded_as_the_caller(client):
    batch = {"events": [{"event_type": "page_view", "user_id": "bob"}]}
    assert (await client.post("/api/v1/events", json=batch)).status_code == 401
    assert (await client.post("/api/v1/events", json=batch, headers=auth("alice", token_type="refresh"))).status_code == 401
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
