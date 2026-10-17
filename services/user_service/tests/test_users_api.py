"""The /users/me endpoints, through the HTTP API."""

import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models.user  # noqa: F401
from app.config import settings
from app.database import Base, get_db
from app.main import app


def auth(sub: str) -> dict:
    token = jwt.encode({"sub": sub, "type": "access"}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {"Authorization": f"Bearer {token}"}


ME = auth("user-1")
ADDRESS = {
    "label": "Home",
    "street": "12 MG Road",
    "city": "Bengaluru",
    "state": "KA",
    "postal_code": "560001",
    "country": "IN",
}


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
async def test_profile_fields_that_always_have_a_value_cannot_be_cleared(client):
    url = "/api/v1/users/me/profile"
    # Not even when the first update creates the profile.
    assert (await client.put(url, json={"language": None}, headers=ME)).status_code == 422
    created = await client.put(url, json={"full_name": "Asha", "language": "hi"}, headers=ME)
    assert created.status_code == 200
    for field in ("language", "timezone"):
        assert (await client.put(url, json={field: None}, headers=ME)).status_code == 422, field
    # Optional details can be cleared, and leaving a field out keeps it.
    cleared = await client.put(url, json={"full_name": None}, headers=ME)
    assert cleared.status_code == 200
    assert (cleared.json()["full_name"], cleared.json()["language"]) == (None, "hi")


@pytest.mark.asyncio
async def test_preferences_and_addresses_cannot_be_set_to_nothing(client):
    prefs = "/api/v1/users/me/preferences"
    for field in ("language", "currency", "theme", "push_enabled"):
        assert (await client.put(prefs, json={field: None}, headers=ME)).status_code == 422, field
    changed = await client.put(prefs, json={"theme": "dark"}, headers=ME)
    assert changed.status_code == 200 and changed.json()["theme"] == "dark"

    address = (await client.post("/api/v1/users/me/addresses", json=ADDRESS, headers=ME)).json()
    url = f"/api/v1/users/me/addresses/{address['id']}"
    for field in ADDRESS:
        assert (await client.put(url, json={field: None}, headers=ME)).status_code == 422, field
    await client.put(url, json={"latitude": 12.97}, headers=ME)
    moved = await client.put(url, json={"latitude": None, "city": "Mysuru"}, headers=ME)
    assert moved.status_code == 200
    assert (moved.json()["latitude"], moved.json()["city"], moved.json()["street"]) == (None, "Mysuru", "12 MG Road")
