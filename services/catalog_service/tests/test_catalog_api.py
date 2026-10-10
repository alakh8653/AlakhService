"""API-level tests that run the real ORM against an in-memory SQLite database."""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models.catalog  # noqa: F401  (registers the models on Base.metadata)
from app.database import Base, get_db
from app.main import app
from app.routers.catalog import get_redis


class FakeRedis:
    def __init__(self):
        self.store = {}

    async def get(self, key):
        return self.store.get(key)

    async def setex(self, key, ttl, value):
        self.store[key] = value

    async def delete(self, key):
        self.store.pop(key, None)


@pytest_asyncio.fixture
async def client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    redis = FakeRedis()

    async def override_get_db():
        async with session_factory() as session:
            yield session
            await session.commit()

    async def override_get_redis():
        yield redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_nested_categories_and_fetch(client):
    resp = await client.post("/api/v1/catalog/categories", json={"name": "Home Cleaning", "slug": "home-cleaning"})
    assert resp.status_code == 201
    parent = resp.json()
    assert parent["parent_id"] is None
    assert parent["children"] == []

    resp = await client.post(
        "/api/v1/catalog/categories",
        json={"name": "Deep Cleaning", "slug": "deep-cleaning", "parent_id": parent["id"]},
    )
    assert resp.status_code == 201
    child = resp.json()

    resp = await client.post(
        "/api/v1/catalog/categories",
        json={"name": "Kitchen", "slug": "kitchen", "parent_id": child["id"]},
    )
    assert resp.status_code == 201

    resp = await client.get(f"/api/v1/catalog/categories/{parent['id']}")
    assert resp.status_code == 200
    assert [c["slug"] for c in resp.json()["children"]] == ["deep-cleaning"]

    resp = await client.get("/api/v1/catalog/categories")
    assert resp.status_code == 200
    assert [c["slug"] for c in resp.json()] == ["home-cleaning"]


@pytest.mark.asyncio
async def test_category_writes_invalidate_cached_tree(client):
    resp = await client.get("/api/v1/catalog/categories/tree")
    assert resp.json() == []  # now cached

    await client.post("/api/v1/catalog/categories", json={"name": "Plumbing", "slug": "plumbing"})

    resp = await client.get("/api/v1/catalog/categories/tree")
    assert [c["slug"] for c in resp.json()] == ["plumbing"]
