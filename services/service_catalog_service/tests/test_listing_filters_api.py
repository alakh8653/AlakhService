"""Listing a shop's services, and who may create or change them."""

import jwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models.catalog  # noqa: F401
from app.config import settings
from app.database import Base, get_db
from app.dependencies import get_shop_listed_lookup, get_shop_owner_lookup, get_shop_types_lookup
from app.main import app

OWNERS = {
    "shop-1": "owner-1",
    "shop-2": "owner-2",
    "shop-new": "owner-3",
    "shop-both": "owner-4",
    "shop-gone": "owner-5",
}
# shop-new still awaits approval in shop_service.
LISTED = {"shop-1": True, "shop-2": True, "shop-new": False, "shop-both": True, "shop-gone": True}
KEY = "internal-test-key"
# Everyone else's only type is electrical; shop-gone is one shop_service could not tell us about.
TYPES = {"shop-both": ["electrical", "plumbing"], "shop-gone": []}


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

    async def fake_types(shop_id):
        return TYPES.get(shop_id, ["electrical"])

    app.dependency_overrides[get_shop_types_lookup] = lambda: fake_types

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


@pytest.mark.asyncio
async def test_browsing_by_type_finds_a_service_whatever_it_is_called(client):
    """A customer tapping Electrical finds "Fan repair", which never says electrical."""
    created = await create_listing(client, "Fan repair")
    found = await client.get("/api/v1/services", params={"category": "electrical"})
    assert [s["id"] for s in found.json()] == [created["id"]]
    assert (await client.get("/api/v1/services", params={"category": "plumbing"})).json() == []
    searched = await client.get("/api/v1/services/search", params={"q": "fan", "category": "electrical"})
    assert [s["id"] for s in searched.json()] == [created["id"]]
    assert (await client.get("/api/v1/services/search", params={"q": "fan", "category": "plumbing"})).json() == []


async def listing_of(client, shop, name, **extra):
    body = {"shop_id": shop, "name": name, "price_cents": 50000, **extra}
    return await client.post("/api/v1/services", json=body, headers=auth(OWNERS[shop]))


async def browse(client, category):
    found = await client.get("/api/v1/services", params={"category": category})
    return sorted(s["name"] for s in found.json())


@pytest.mark.asyncio
async def test_a_provider_with_two_types_is_found_under_either(client):
    fan = await listing_of(client, "shop-both", "Fan repair", service_type="electrical")
    tap = await listing_of(client, "shop-both", "Tap repair", service_type="plumbing")
    assert (fan.status_code, tap.status_code) == (201, 201)
    assert tap.json()["service_type"] == "plumbing"
    assert await browse(client, "electrical") == ["Fan repair"]
    assert await browse(client, "plumbing") == ["Tap repair"]

    async def searched(category, q=None):
        params = {"category": category, **({"q": q} if q else {})}
        return [s["name"] for s in (await client.get("/api/v1/services/search", params=params)).json()]

    assert await searched("plumbing") == ["Tap repair"]
    assert await searched("plumbing", "repair") == ["Tap repair"]
    assert await searched("electrical", "repair") == ["Fan repair"]
    assert await searched("plumbing", "fan") == []


@pytest.mark.asyncio
async def test_a_service_without_a_type_stays_under_the_main_type_of_its_shop(client):
    """Every service from before there were several types, and any single-type shop's."""
    created = await listing_of(client, "shop-1", "Fan repair")
    assert created.json()["service_type"] is None
    assert await browse(client, "electrical") == ["Fan repair"]
    assert await browse(client, "plumbing") == []


@pytest.mark.asyncio
async def test_a_service_cannot_go_under_a_type_its_shop_did_not_choose(client):
    """The documents are checked per type, so this would list a salon under clinics without any."""
    refused = await listing_of(client, "shop-both", "Consultation", service_type="clinic")
    assert refused.status_code == 422
    assert await browse(client, "clinic") == []
    fan = await listing_of(client, "shop-1", "Fan repair", service_type="electrical")
    assert fan.status_code == 201
    moved = await client.put(
        f"/api/v1/services/{fan.json()['id']}", json={"service_type": "clinic"}, headers=auth("owner-1")
    )
    assert moved.status_code == 422
    assert await browse(client, "clinic") == []
    # And when shop_service cannot say, it is not taken on trust.
    assert (await listing_of(client, "shop-gone", "Fan repair", service_type="clinic")).status_code == 503
    assert (await listing_of(client, "shop-gone", "Fan repair")).status_code == 201


@pytest.mark.asyncio
async def test_a_service_can_move_to_another_of_the_shops_types(client):
    created = await listing_of(client, "shop-both", "Geyser fitting")
    assert await browse(client, "electrical") == ["Geyser fitting"]
    url = f"/api/v1/services/{created.json()['id']}"
    moved = await client.put(url, json={"service_type": "plumbing"}, headers=auth("owner-4"))
    assert moved.json()["service_type"] == "plumbing"
    assert (await browse(client, "electrical"), await browse(client, "plumbing")) == ([], ["Geyser fitting"])
    back = await client.put(url, json={"service_type": None}, headers=auth("owner-4"))
    assert back.json()["service_type"] is None
    assert await browse(client, "electrical") == ["Geyser fitting"]


@pytest.mark.asyncio
async def test_dropping_a_type_brings_its_services_back_under_the_main_one(client, monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", KEY)
    await listing_of(client, "shop-both", "Tap repair", service_type="plumbing")
    await listing_of(client, "shop-both", "Fan repair", service_type="electrical")
    await listing_of(client, "shop-both", "Wiring")
    url = "/internal/shops/shop-both/listing"
    headers = {"X-Internal-Key": KEY}

    # An older shop_service, or a message about listing only, leaves the types alone.
    await client.post(url, json={"listed": True, "category": "electrical"}, headers=headers)
    await client.post(url, json={"listed": True}, headers=headers)
    assert await browse(client, "plumbing") == ["Tap repair"]

    body = {"listed": True, "category": "electrical", "extra_categories": ["plumbing"]}
    assert (await client.post(url, json=body, headers=headers)).status_code == 200
    assert await browse(client, "plumbing") == ["Tap repair"]

    body["extra_categories"] = []
    await client.post(url, json=body, headers=headers)
    assert await browse(client, "plumbing") == []
    assert await browse(client, "electrical") == ["Fan repair", "Tap repair", "Wiring"]


@pytest.mark.asyncio
async def test_a_single_type_shop_moving_trade_takes_all_its_services_along(client, monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", KEY)
    await listing_of(client, "shop-1", "Old", service_type="electrical")
    await listing_of(client, "shop-1", "Older")
    body = {"listed": True, "category": "plumbing", "extra_categories": []}
    await client.post("/internal/shops/shop-1/listing", json=body, headers={"X-Internal-Key": KEY})
    assert await browse(client, "plumbing") == ["Old", "Older"]
    assert await browse(client, "electrical") == []
