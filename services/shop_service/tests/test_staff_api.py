"""Shop ownership checks and staff management."""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models.shop  # noqa: F401
from app.database import Base, get_db
from app.main import app

OWNER = {"x-user-id": "owner-1"}
OTHER = {"x-user-id": "owner-2"}
ADMIN = {"x-user-id": "ops", "x-user-role": "admin"}


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


async def make_shop(client, owner="owner-1", name="Glow Salon"):
    resp = await client.post("/api/v1/shops", json={"owner_id": owner, "name": name, "category": "salon"})
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_owner_filter_includes_inactive_shops(client):
    mine = await make_shop(client)
    await make_shop(client, owner="owner-2", name="Other")
    await client.put(f"/api/v1/shops/{mine['id']}", json={"is_active": False})

    owned = (await client.get("/api/v1/shops", params={"owner_id": "owner-1"})).json()
    assert [s["id"] for s in owned] == [mine["id"]]
    public = (await client.get("/api/v1/shops")).json()
    assert mine["id"] not in [s["id"] for s in public]


@pytest.mark.asyncio
async def test_only_owner_or_admin_can_edit_a_shop_through_the_gateway(client):
    shop = await make_shop(client)
    url = f"/api/v1/shops/{shop['id']}"
    assert (await client.put(url, json={"phone": "+911234567"}, headers=OTHER)).status_code == 403
    updated = await client.put(url, json={"phone": "+911234567", "address": "1 MG Road"}, headers=OWNER)
    assert updated.status_code == 200
    assert updated.json()["phone"] == "+911234567"
    assert updated.json()["address"] == "1 MG Road"
    assert (await client.put(url, json={"email": "a@b.c"}, headers=ADMIN)).status_code == 200


@pytest.mark.asyncio
async def test_staff_lifecycle_and_access(client):
    shop = await make_shop(client)
    body = {"shop_id": shop["id"], "name": "Asha", "role": "stylist", "service_ids": ["s2", "s1", "s1"]}

    assert (await client.post("/api/v1/staff", json=body)).status_code == 401
    assert (await client.post("/api/v1/staff", json=body, headers=OTHER)).status_code == 403

    created = await client.post("/api/v1/staff", json=body, headers=OWNER)
    assert created.status_code == 201
    member = created.json()
    assert member["service_ids"] == ["s1", "s2"]

    listed = (await client.get("/api/v1/staff", params={"shop_id": shop["id"]}, headers=OWNER)).json()
    assert [m["name"] for m in listed] == ["Asha"]
    assert (await client.get("/api/v1/staff", params={"shop_id": shop["id"]}, headers=OTHER)).status_code == 403

    upd = await client.put(f"/api/v1/staff/{member['id']}", json={"is_active": False}, headers=OWNER)
    assert upd.json()["is_active"] is False
    assert (await client.get("/api/v1/staff", params={"shop_id": shop["id"]}, headers=OWNER)).json() == []
    all_staff = (
        await client.get("/api/v1/staff", params={"shop_id": shop["id"], "include_inactive": True}, headers=OWNER)
    ).json()
    assert len(all_staff) == 1

    assert (await client.delete(f"/api/v1/staff/{member['id']}", headers=OTHER)).status_code == 403
    assert (await client.delete(f"/api/v1/staff/{member['id']}", headers=ADMIN)).status_code == 204
    assert (await client.put(f"/api/v1/staff/{member['id']}", json={}, headers=OWNER)).status_code == 404
