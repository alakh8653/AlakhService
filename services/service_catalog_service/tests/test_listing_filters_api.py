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
from app.dependencies import get_shop_listed_lookup, get_shop_owner_lookup
from app.main import app

OWNERS = {"shop-1": "owner-1", "shop-2": "owner-2", "shop-new": "owner-3"}
# shop-new still awaits approval in shop_service.
LISTED = {"shop-1": True, "shop-2": True, "shop-new": False}
KEY = "internal-test-key"


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

    async def fake_listed(shop_id):
        return LISTED[shop_id]

    app.dependency_overrides[get_shop_owner_lookup] = lambda: fake_owner
    app.dependency_overrides[get_shop_listed_lookup] = lambda: fake_listed
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


@pytest.mark.asyncio
async def test_services_say_how_they_are_delivered(client):
    owner = auth("owner-1")
    # Default: the customer comes to the shop, no extra fees.
    plain = (
        await client.post(
            "/api/v1/services", json={"shop_id": "shop-1", "name": "Haircut", "price_cents": 30000}, headers=owner
        )
    ).json()
    assert (plain["service_modes"], plain["home_visit_fee_cents"], plain["pickup_fee_cents"]) == (["AT_SHOP"], 0, 0)

    repair = {
        "shop_id": "shop-1",
        "name": "Laptop screen repair",
        "price_cents": 450000,
        "service_modes": ["AT_SHOP", "PICKUP_DROP", "PICKUP_DROP"],
        "pickup_fee_cents": 9900,
    }
    created = await client.post("/api/v1/services", json=repair, headers=owner)
    assert created.status_code == 201
    assert created.json()["service_modes"] == ["AT_SHOP", "PICKUP_DROP"]  # duplicates dropped
    assert (await client.get(f"/api/v1/services/{created.json()['id']}")).json()["pickup_fee_cents"] == 9900

    for bad in ({"service_modes": []}, {"service_modes": ["TELEPORT"]}, {"pickup_fee_cents": -1}):
        resp = await client.post("/api/v1/services", json={**repair, **bad}, headers=owner)
        assert resp.status_code == 422, bad

    # The shop starts doing home visits for haircuts, with a fee.
    updated = await client.put(
        f"/api/v1/services/{plain['id']}",
        json={"service_modes": ["AT_SHOP", "AT_HOME"], "home_visit_fee_cents": 15000},
        headers=owner,
    )
    assert (updated.json()["service_modes"], updated.json()["home_visit_fee_cents"]) == (["AT_SHOP", "AT_HOME"], 15000)
    # Updating something else leaves the modes alone.
    renamed = await client.put(f"/api/v1/services/{plain['id']}", json={"name": "Haircut & style"}, headers=owner)
    assert renamed.json()["service_modes"] == ["AT_SHOP", "AT_HOME"]


async def create_listing(client, name: str, **extra) -> dict:
    body = {"shop_id": "shop-1", "name": name, "price_cents": 50000, **extra}
    resp = await client.post("/api/v1/services", json=body, headers=auth("owner-1"))
    assert resp.status_code == 201, resp.text
    return resp.json()


async def search(client, **params) -> list:
    resp = await client.get("/api/v1/services/search", params=params)
    assert resp.status_code == 200, resp.text
    return [s["id"] for s in resp.json()]


@pytest.mark.asyncio
async def test_search_returns_only_matching_listings_best_first_and_follows_edits(client):
    beard = await create_listing(client, "Haircut and beard trim")
    haircut = await create_listing(client, "Haircut")
    await create_listing(client, "Deep tissue massage")

    assert await search(client, q="haircut") == [haircut["id"], beard["id"]]

    owner = auth("owner-1")
    await client.put(f"/api/v1/services/{haircut['id']}", json={"name": "Buzz cut"}, headers=owner)
    assert await search(client, q="haircut") == [beard["id"]]
    assert await search(client, q="buzz") == [haircut["id"]]

    await client.put(f"/api/v1/services/{beard['id']}", json={"is_active": False}, headers=owner)
    assert await search(client, q="beard trim") == []


@pytest.mark.asyncio
async def test_search_index_is_rebuilt_from_the_database_after_a_restart(client):
    from app.services import catalog_service as module

    massage = await create_listing(client, "Deep tissue massage")
    # A fresh process starts with an empty in-memory index.
    module._tfidf_index.clear()
    module._index_state["loaded"] = False
    assert await search(client, q="tissue deep") == [massage["id"]]


@pytest.mark.asyncio
async def test_listing_and_search_pages_are_bounded(client):
    for name in ("Alpha", "Beta", "Gamma"):
        await create_listing(client, name)
    assert len(await search(client, limit=2)) == 2
    assert (await client.get("/api/v1/services/search", params={"limit": 0})).status_code == 422
    assert (await client.get("/api/v1/services/search", params={"limit": 101})).status_code == 422
    assert (await client.get("/api/v1/services", params={"skip": -1})).status_code == 422
    assert (await client.get("/api/v1/services", params={"limit": 0})).status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad",
    [{"price_cents": -1}, {"duration_minutes": 0}, {"duration_minutes": -30}, {"home_visit_fee_cents": -1}],
)
async def test_negative_prices_and_durations_are_rejected(client, bad):
    owner = auth("owner-1")
    body = {"shop_id": "shop-1", "name": "Haircut", "price_cents": 50000}
    assert (await client.post("/api/v1/services", json={**body, **bad}, headers=owner)).status_code == 422
    listing = await create_listing(client, "Haircut")
    resp = await client.put(f"/api/v1/services/{listing['id']}", json=bad, headers=owner)
    assert resp.status_code == 422
    assert (await client.get(f"/api/v1/services/{listing['id']}")).json()["price_cents"] == 50000


@pytest.mark.asyncio
async def test_services_of_a_shop_awaiting_approval_stay_hidden_until_it_is_approved(client, monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", KEY)
    body = {"shop_id": "shop-new", "name": "Bridal makeup", "price_cents": 900000}
    created = await client.post("/api/v1/services", json=body, headers=auth("owner-3"))
    assert created.status_code == 201
    listed = {"shop_id": "shop-1", "name": "Bridal hair", "price_cents": 500000}
    assert (await client.post("/api/v1/services", json=listed, headers=auth("owner-1"))).status_code == 201

    def names(resp):
        return sorted(s["name"] for s in resp.json())

    assert names(await client.get("/api/v1/services")) == ["Bridal hair"]
    assert names(await client.get("/api/v1/services/search", params={"q": "bridal"})) == ["Bridal hair"]
    # The owner's dashboard still lists it, and booking_service can still look it up by id.
    assert names(await client.get("/api/v1/services", params={"shop_id": "shop-new"})) == ["Bridal makeup"]
    assert (await client.get(f"/api/v1/services/{created.json()['id']}")).status_code == 200

    approve = "/internal/shops/shop-new/listing"
    assert (await client.post(approve, json={"listed": True})).status_code == 401
    done = await client.post(approve, json={"listed": True}, headers={"X-Internal-Key": KEY})
    assert done.json() == {"shop_id": "shop-new", "listed": True, "changed": 1}
    assert names(await client.get("/api/v1/services/search", params={"q": "bridal"})) == [
        "Bridal hair",
        "Bridal makeup",
    ]
