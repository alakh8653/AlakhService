"""Listing a shop's services, including deactivated ones for its owner."""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models.catalog  # noqa: F401
from app.database import Base, get_db
from app.main import app


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
async def test_filter_by_shop_and_include_inactive(client):
    async def create(shop, name):
        resp = await client.post("/api/v1/services", json={"shop_id": shop, "name": name, "price_cents": 50000})
        assert resp.status_code == 201
        return resp.json()

    haircut = await create("shop-1", "Haircut")
    colour = await create("shop-1", "Colour")
    await create("shop-2", "Massage")
    await client.put(f"/api/v1/services/{colour['id']}", json={"is_active": False})

    active = (await client.get("/api/v1/services", params={"shop_id": "shop-1"})).json()
    assert [s["id"] for s in active] == [haircut["id"]]

    everything = (await client.get("/api/v1/services", params={"shop_id": "shop-1", "include_inactive": True})).json()
    assert [s["name"] for s in everything] == ["Colour", "Haircut"]

    assert len((await client.get("/api/v1/services")).json()) == 2  # all shops, active only
