"""Listing a shop's services, and who may create or change them."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models.catalog  # noqa: F401
from app.config import settings
from app.database import Base, get_db
from app.dependencies import get_shop_owner_lookup
from app.main import app

OWNERS = {"shop-1": "owner-1", "shop-2": "owner-2"}


def auth(sub: str, role: str = "user") -> dict:
    token = jwt.encode({"sub": sub, "role": role, "type": "access"}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {"Authorization": f"Bearer {token}"}


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

    async def fake_owner(shop_id):
        return OWNERS.get(shop_id)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_shop_owner_lookup] = lambda: fake_owner
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_filter_by_shop_and_include_inactive(client):
    async def create(shop, name):
        body = {"shop_id": shop, "name": name, "price_cents": 50000}
        resp = await client.post("/api/v1/services", json=body, headers=auth(OWNERS[shop]))
        assert resp.status_code == 201
        return resp.json()

    haircut = await create("shop-1", "Haircut")
    colour = await create("shop-1", "Colour")
    await create("shop-2", "Massage")
    await client.put(f"/api/v1/services/{colour['id']}", json={"is_active": False}, headers=auth("owner-1"))

    active = (await client.get("/api/v1/services", params={"shop_id": "shop-1"})).json()
    assert [s["id"] for s in active] == [haircut["id"]]

    everything = (await client.get("/api/v1/services", params={"shop_id": "shop-1", "include_inactive": True})).json()
    assert [s["name"] for s in everything] == ["Colour", "Haircut"]

    assert len((await client.get("/api/v1/services")).json()) == 2  # all shops, active only


@pytest.mark.asyncio
async def test_only_the_shop_owner_or_an_admin_manages_listings(client):
    body = {"shop_id": "shop-1", "name": "Haircut", "price_cents": 50000}
    assert (await client.post("/api/v1/services", json=body)).status_code == 401
    assert (await client.post("/api/v1/services", json=body, headers=auth("owner-2"))).status_code == 403
    assert (
        await client.post("/api/v1/services", json={**body, "shop_id": "nope"}, headers=auth("owner-1"))
    ).status_code == 404
    created = await client.post("/api/v1/services", json=body, headers=auth("owner-1"))
    assert created.status_code == 201

    url = f"/api/v1/services/{created.json()['id']}"
    assert (await client.put(url, json={"price_cents": 1})).status_code == 401
    assert (await client.put(url, json={"price_cents": 1}, headers=auth("owner-2"))).status_code == 403
    assert (await client.put(url, json={"price_cents": 45000}, headers=auth("owner-1"))).json()["price_cents"] == 45000
    assert (await client.put(url, json={"is_active": False}, headers=auth("ops", "admin"))).status_code == 200
    assert (await client.put("/api/v1/services/missing", json={}, headers=auth("owner-1"))).status_code == 404


@pytest.mark.asyncio
async def test_only_admins_create_categories(client):
    assert (
        await client.post("/api/v1/categories", json={"name": "Hair", "slug": "hair"}, headers=auth("owner-1"))
    ).status_code == 403
    assert (
        await client.post("/api/v1/categories", json={"name": "Hair", "slug": "hair"}, headers=auth("ops", "admin"))
    ).status_code == 201
