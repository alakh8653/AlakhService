"""Providers report only their own location; geofences are created by admins."""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models.tracking  # noqa: F401  (registers the models on Base.metadata)
from app.config import settings
from app.database import Base, get_db
from app.dependencies import get_tracking_check
from app.main import app


def auth(sub: str, role: str = "user", token_type: str = "access") -> dict:
    token = jwt.encode({"sub": sub, "role": role, "type": token_type}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {"Authorization": f"Bearer {token}"}


ALICE, BOB, ADMIN = auth("alice"), auth("bob"), auth("ops", "admin")
SERVING = {("carol", "bob")}  # carol has a booking bob is working on


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

    async def tracking_check(provider_id, caller):
        return (caller.user_id, provider_id) in SERVING  # who booking_service says is being served

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_tracking_check] = lambda: tracking_check
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_tracking_rules(client):
    location = {"provider_id": "bob", "latitude": 18.52, "longitude": 73.85}
    assert (await client.post("/api/v1/locations", json=location)).status_code == 401
    assert (await client.post("/api/v1/locations", json=location, headers=ALICE)).status_code == 403
    assert (await client.post("/api/v1/locations", json=location, headers=BOB)).status_code == 201
    assert (await client.get("/api/v1/locations/bob")).status_code == 401
    assert (await client.get("/api/v1/locations/bob", headers=ALICE)).status_code == 404  # not her provider
    assert (await client.get("/api/v1/locations/bob", headers=auth("carol"))).status_code == 200
    assert (await client.get("/api/v1/locations/bob", headers=BOB)).status_code == 200
    assert (await client.get("/api/v1/locations/bob", headers=ADMIN)).status_code == 200

    fence = {"name": "Pune", "center_lat": 18.52, "center_lng": 73.85, "radius_meters": 5000}
    assert (await client.post("/api/v1/geofences", json=fence, headers=ALICE)).status_code == 403
