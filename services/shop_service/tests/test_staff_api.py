"""Shop ownership checks and staff management."""

from urllib.parse import unquote

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models.shop  # noqa: F401
from app.config import settings
from app.database import Base, get_db
from app.dependencies import get_booking_lookup
from app.main import app


def auth(sub: str, role: str = "user", token_type: str = "access") -> dict:
    token = jwt.encode(
        {"sub": sub, "role": role, "type": token_type}, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return {"Authorization": f"Bearer {token}"}


BOOKINGS = {}

OWNER = auth("owner-1")
OTHER = auth("owner-2")
ADMIN = auth("ops", "admin")


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

    async def fake_booking(booking_id, caller):
        booking = BOOKINGS.get(booking_id)
        # booking_service only shows a booking to its parties.
        return booking if booking and caller.user_id in (booking["customer_id"], "ops") else None

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_booking_lookup] = lambda: fake_booking
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
    await engine.dispose()


async def make_shop(client, owner="owner-1", name="Glow Salon"):
    resp = await client.post(
        "/api/v1/shops", json={"owner_id": owner, "name": name, "category": "salon"}, headers=auth(owner)
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_owner_filter_includes_inactive_shops(client):
    mine = await make_shop(client)
    await make_shop(client, owner="owner-2", name="Other")
    await client.put(f"/api/v1/shops/{mine['id']}", json={"is_active": False}, headers=OWNER)

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


@pytest.mark.asyncio
async def test_shops_are_created_and_deleted_only_by_their_owner(client):
    body = {"owner_id": "owner-1", "name": "Mine", "category": "salon"}
    assert (await client.post("/api/v1/shops", json=body)).status_code == 401
    assert (await client.post("/api/v1/shops", json=body, headers=OTHER)).status_code == 403
    shop = await make_shop(client)
    # One shop per owner: a second submit is refused, though admins may still open more on their behalf.
    assert (await client.post("/api/v1/shops", json=body, headers=OWNER)).status_code == 409
    assert (await client.post("/api/v1/shops", json=body, headers=ADMIN)).status_code == 201

    url = f"/api/v1/shops/{shop['id']}"
    assert (await client.put(url, json={"name": "Renamed"})).status_code == 401
    assert (await client.delete(url)).status_code == 401
    assert (await client.delete(url, headers=OTHER)).status_code == 403
    assert (await client.delete(url, headers=OWNER)).status_code == 204


@pytest.mark.asyncio
async def test_only_signed_access_tokens_identify_the_caller(client):
    shop = await make_shop(client)
    url = f"/api/v1/shops/{shop['id']}"
    # Gateway-style identity headers are not trusted on their own...
    assert (await client.put(url, json={"name": "X"}, headers={"x-user-id": "owner-1"})).status_code == 401
    # ...and neither are refresh tokens or tokens signed with another key.
    assert (await client.put(url, json={"name": "X"}, headers=auth("owner-1", token_type="refresh"))).status_code == 401
    forged = jwt.encode({"sub": "owner-1", "type": "access"}, "not-the-key", algorithm="HS256")
    assert (await client.put(url, json={"name": "X"}, headers={"Authorization": f"Bearer {forged}"})).status_code == 401


@pytest.mark.asyncio
async def test_customers_rate_a_shop_once_per_completed_booking(client):
    shop = await make_shop(client)
    other = await make_shop(client, owner="owner-2", name="Other")
    BOOKINGS.clear()
    BOOKINGS.update(
        {
            "done": {"id": "done", "customer_id": "cust-1", "shop_id": shop["id"], "status": "COMPLETED"},
            "pending": {"id": "pending", "customer_id": "cust-1", "shop_id": shop["id"], "status": "PENDING"},
            "elsewhere": {"id": "elsewhere", "customer_id": "cust-1", "shop_id": other["id"], "status": "COMPLETED"},
        }
    )
    url = f"/api/v1/shops/{shop['id']}/rating"
    customer = auth("cust-1")

    assert (await client.post(url, json={"booking_id": "done", "rating": 5})).status_code == 401
    assert (
        await client.post(url, json={"booking_id": "done", "rating": 5}, headers=auth("stranger"))
    ).status_code == 404
    assert (await client.post(url, json={"booking_id": "elsewhere", "rating": 5}, headers=customer)).status_code == 404
    assert (await client.post(url, json={"booking_id": "pending", "rating": 5}, headers=customer)).status_code == 409
    assert (await client.post(url, json={"booking_id": "done", "rating": 50}, headers=customer)).status_code == 422

    rated = await client.post(url, json={"booking_id": "done", "rating": 4, "comment": "Great cut"}, headers=customer)
    assert rated.status_code == 200
    assert rated.json()["rating_avg"] == 4.0 and rated.json()["rating_count"] == 1
    assert (await client.post(url, json={"booking_id": "done", "rating": 1}, headers=customer)).status_code == 409


@pytest.mark.asyncio
async def test_shop_lists_are_paged_within_bounds(client):
    for n in range(3):
        await make_shop(client, owner=f"owner-{n}", name=f"Glow Salon {n}")
    for params in ({"skip": -1}, {"limit": 0}, {"limit": -1}, {"limit": 101}):
        assert (await client.get("/api/v1/shops", params=params)).status_code == 422
    everything = [s["id"] for s in (await client.get("/api/v1/shops", params={"limit": 100})).json()]
    assert len(everything) == 3
    page = (await client.get("/api/v1/shops", params={"skip": 1, "limit": 1})).json()
    assert [s["id"] for s in page] == everything[1:2]

    # Search is bounded the same way.
    for limit in (0, 101):
        assert (await client.get("/api/v1/shops/search", params={"q": "Glow", "limit": limit})).status_code == 422
    found = (await client.get("/api/v1/shops/search", params={"q": "Glow", "limit": 2})).json()
    assert [s["id"] for s in found] == everything[:2]
    assert len((await client.get("/api/v1/shops/search", params={"q": "Glow"})).json()) == 3


@pytest.mark.asyncio
async def test_fields_a_shop_always_has_cannot_be_cleared(client):
    shop = await make_shop(client)
    url = f"/api/v1/shops/{shop['id']}"
    for field in ("name", "category", "is_active"):
        assert (await client.put(url, json={field: None}, headers=OWNER)).status_code == 422, field
    # Optional details can be cleared, and leaving a field out keeps it.
    await client.put(url, json={"phone": "+911234567"}, headers=OWNER)
    cleared = await client.put(url, json={"phone": None}, headers=OWNER)
    assert cleared.status_code == 200
    assert (cleared.json()["phone"], cleared.json()["name"], cleared.json()["is_active"]) == (None, "Glow Salon", True)

    staff = await client.post("/api/v1/staff", json={"shop_id": shop["id"], "name": "Asha"}, headers=OWNER)
    staff_url = f"/api/v1/staff/{staff.json()['id']}"
    for field in ("name", "role", "is_active"):
        assert (await client.put(staff_url, json={field: None}, headers=OWNER)).status_code == 422, field
    # No services is a value of its own.
    none = await client.put(staff_url, json={"service_ids": None}, headers=OWNER)
    assert none.status_code == 200 and none.json()["service_ids"] == []


@pytest.mark.asyncio
async def test_a_booking_id_from_the_client_stays_one_path_segment(monkeypatch):
    import httpx

    from app import dependencies

    paths = []

    def booking_service(request):
        paths.append(request.url.raw_path)
        return httpx.Response(404)

    real = httpx.AsyncClient
    monkeypatch.setattr(
        dependencies.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(booking_service), **kw)
    )
    ids = ["..", "../shops/x", "bk-1?status=COMPLETED#x", "%2e%2e"]
    for booking_id in ids:
        assert await dependencies.fetch_booking(booking_id, dependencies.Caller("cust-1", "user", "t")) is None
    prefix = b"/api/v1/bookings/"
    assert all(p.startswith(prefix) and b"/" not in p[len(prefix) :] and b"?" not in p for p in paths)
    assert [unquote(p[len(prefix) :].decode()) for p in paths] == ids
