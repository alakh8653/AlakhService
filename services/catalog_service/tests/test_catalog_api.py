"""API-level tests that run the real ORM against an in-memory SQLite database."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models.catalog  # noqa: F401  (registers the models on Base.metadata)
from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models.catalog import ServiceItem
from app.routers.catalog import get_redis


def auth(sub: str, role: str = "admin") -> dict:
    token = jwt.encode({"sub": sub, "role": role, "type": "access"}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {"Authorization": f"Bearer {token}"}


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
    # Catalogue changes are admin-only; requests are made as an admin unless a test says otherwise.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers=auth("ops")) as ac:
        ac.session_factory = session_factory
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


@pytest.mark.asyncio
async def test_browsing_is_public_but_changes_are_admin_only(client):
    category = {"name": "Painting", "slug": "painting"}
    assert (
        await client.post("/api/v1/catalog/categories", json=category, headers={"Authorization": ""})
    ).status_code == 401
    assert (
        await client.post("/api/v1/catalog/categories", json=category, headers=auth("u1", "user"))
    ).status_code == 403
    assert (await client.post("/api/v1/catalog/categories", json=category)).status_code == 201
    assert (await client.get("/api/v1/catalog/categories", headers={"Authorization": ""})).status_code == 200


async def create_item(client, slug: str, **extra) -> dict:
    resp = await client.post(
        "/api/v1/catalog/services", json={"name": slug.title(), "slug": slug, "base_price_cents": 1000, **extra}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_created_service_is_returned_and_readable_with_its_metadata(client):
    created = await create_item(client, "ac-repair", metadata={"brand": "any"})
    assert created["metadata"] == {"brand": "any"}
    assert created["pricing_tiers"] == [] and created["media"] == [] and created["variants"] == []

    resp = await client.get(f"/api/v1/catalog/services/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["metadata"] == {"brand": "any"}
    assert (await client.get("/api/v1/catalog/services/slug/ac-repair")).json()["id"] == created["id"]
    listed = (await client.get("/api/v1/catalog/services")).json()
    assert [i["slug"] for i in listed["items"]] == ["ac-repair"]


@pytest.mark.asyncio
async def test_duplicate_service_slug_is_a_conflict(client):
    await create_item(client, "plumbing")
    other = await create_item(client, "painting")
    resp = await client.post("/api/v1/catalog/services", json={"name": "P", "slug": "plumbing", "base_price_cents": 1})
    assert resp.status_code == 409
    resp = await client.put(f"/api/v1/catalog/services/{other['id']}", json={"slug": "plumbing"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_featured_list_drops_deleted_services_and_sees_new_ones(client):
    first = await create_item(client, "deep-clean", is_featured=True)
    assert [s["id"] for s in (await client.get("/api/v1/catalog/services/featured")).json()] == [first["id"]]

    second = await create_item(client, "sofa-clean", is_featured=True)
    assert (await client.delete(f"/api/v1/catalog/services/{first['id']}")).status_code == 200
    assert [s["id"] for s in (await client.get("/api/v1/catalog/services/featured")).json()] == [second["id"]]

    await client.put(f"/api/v1/catalog/services/{second['id']}", json={"is_featured": False})
    assert (await client.get("/api/v1/catalog/services/featured")).json() == []


@pytest.mark.asyncio
async def test_popular_list_keeps_booking_rank_when_served_from_cache(client):
    ids = {slug: (await create_item(client, slug))["id"] for slug in ("a", "b", "c")}
    async with client.session_factory() as session:
        for slug, count in (("a", 1), ("b", 50), ("c", 10)):
            await session.execute(update(ServiceItem).where(ServiceItem.id == ids[slug]).values(booking_count=count))
        await session.commit()

    expected = [ids["b"], ids["c"], ids["a"]]
    assert [s["id"] for s in (await client.get("/api/v1/catalog/services/popular")).json()] == expected
    assert [s["id"] for s in (await client.get("/api/v1/catalog/services/popular")).json()] == expected
    assert [s["id"] for s in (await client.get("/api/v1/catalog/services/popular?limit=2")).json()] == expected[:2]

    # Deactivated after caching: dropped from the cached ranking without a DB-side rebuild.
    async with client.session_factory() as session:
        await session.execute(update(ServiceItem).where(ServiceItem.id == ids["b"]).values(is_active=False))
        await session.commit()
    assert [s["id"] for s in (await client.get("/api/v1/catalog/services/popular")).json()] == expected[1:]


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [{"page": 0}, {"page": -1}, {"per_page": 0}, {"per_page": -5}, {"per_page": 101}])
async def test_search_rejects_out_of_range_pagination(client, body):
    assert (await client.post("/api/v1/catalog/services/search", json=body)).status_code == 422
