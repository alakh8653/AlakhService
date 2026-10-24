"""Other services (auth_service at sign-up) record consents with the internal key."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models.compliance  # noqa: F401  (registers the models on Base.metadata)
from app.config import settings
from app.database import Base, get_db
from app.main import app

KEY = "internal-test-key"


def auth(sub: str) -> dict:
    token = jwt.encode(
        {"sub": sub, "role": "user", "type": "access"}, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def client(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", KEY)
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


CONSENT = {
    "user_id": "alice",
    "consent_type": "terms",
    "version": "2026-10",
    "ip_address": "203.0.113.9",
    "user_agent": "AlakhApp/1.0",
}


@pytest.mark.asyncio
async def test_a_service_records_a_consent_with_the_persons_ip(client):
    resp = await client.post("/internal/consent", json=CONSENT, headers={"X-Internal-Key": KEY})
    assert resp.status_code == 201
    assert resp.json()["granted"] is True

    mine = (await client.get("/api/v1/consent/alice", headers=auth("alice"))).json()
    assert [(c["consent_type"], c["version"], c["ip_address"], c["user_agent"]) for c in mine] == [
        ("terms", "2026-10", "203.0.113.9", "AlakhApp/1.0")
    ]


@pytest.mark.asyncio
async def test_only_services_holding_the_key_record_consents(client, monkeypatch):
    assert (await client.post("/internal/consent", json=CONSENT)).status_code == 401
    assert (await client.post("/internal/consent", json=CONSENT, headers=auth("alice"))).status_code == 401
    assert (
        await client.post("/api/v1/internal/consent", json=CONSENT, headers={"X-Internal-Key": KEY})
    ).status_code == 404
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", "")
    assert (await client.post("/internal/consent", json=CONSENT, headers={"X-Internal-Key": ""})).status_code == 503
