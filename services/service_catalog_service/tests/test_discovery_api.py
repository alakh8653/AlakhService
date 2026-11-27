"""Browsing and searching with filters and sort orders: price, rating, delivery mode, distance."""

import pytest

from app.config import settings
from app.core.discovery import distance_km
from tests.test_listing_filters_api import KEY, OWNERS, auth, client  # noqa: F401  (client is a fixture)

# Pune: the customer stands at FC Road.
HERE = {"lat": 18.5236, "lng": 73.8478}
# shop-1 is about 1 km away (Deccan), shop-2 about 12 km (Hadapsar).
FACTS = {
    "shop-1": {"latitude": 18.5167, "longitude": 73.8414, "rating": 4.6, "rating_count": 38},
    "shop-2": {"latitude": 18.5089, "longitude": 73.9260, "rating": 3.9, "rating_count": 12},
}


@pytest.fixture
def internal(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", KEY)
    return {"X-Internal-Key": KEY}


async def seed(client, internal):  # noqa: F811
    async def create(shop, name, price, modes=("AT_SHOP",)):
        body = {"shop_id": shop, "name": name, "price_cents": price, "service_modes": list(modes)}
        resp = await client.post("/api/v1/services", json=body, headers=auth(OWNERS[shop]))
        assert resp.status_code == 201
        return resp.json()["id"]

    ids = {
        "cut1": await create("shop-1", "Haircut", 30000),
        "beard1": await create("shop-1", "Beard trim", 15000, ("AT_SHOP", "AT_HOME")),
        "cut2": await create("shop-2", "Haircut deluxe", 60000, ("AT_HOME",)),
    }
    for shop, facts in FACTS.items():
        resp = await client.post(
            f"/internal/shops/{shop}/listing", json={"listed": True, "facts": facts}, headers=internal
        )
        assert resp.status_code == 200
    return ids


def names(resp):
    assert resp.status_code == 200, resp.text
    return [s["name"] for s in resp.json()]


@pytest.mark.asyncio
async def test_price_rating_and_mode_filters(client, internal):  # noqa: F811
    await seed(client, internal)
    browse = lambda **p: client.get("/api/v1/services", params=p)  # noqa: E731
    assert names(await browse(max_price=300)) == ["Beard trim", "Haircut"]
    assert names(await browse(min_price=200, max_price=600)) == ["Haircut", "Haircut deluxe"]
    assert names(await browse(min_rating=4.5)) == ["Beard trim", "Haircut"]
    assert names(await browse(mode="AT_HOME")) == ["Beard trim", "Haircut deluxe"]
    assert names(await browse(mode="AT_HOME", min_rating=4)) == ["Beard trim"]
    # Searching takes the same filters.
    assert names(await client.get("/api/v1/services/search", params={"q": "haircut", "mode": "AT_HOME"})) == [
        "Haircut deluxe"
    ]


@pytest.mark.asyncio
async def test_sort_orders(client, internal):  # noqa: F811
    await seed(client, internal)
    browse = lambda **p: client.get("/api/v1/services", params=p)  # noqa: E731
    assert names(await browse(sort="price_asc")) == ["Beard trim", "Haircut", "Haircut deluxe"]
    assert names(await browse(sort="price_desc")) == ["Haircut deluxe", "Haircut", "Beard trim"]
    assert names(await browse(sort="rating"))[-1] == "Haircut deluxe"
    rated = (await browse(sort="rating")).json()[0]
    assert (rated["shop_rating"], rated["shop_rating_count"]) == (4.6, 38)


@pytest.mark.asyncio
async def test_nearest_first_with_distances_and_a_radius(client, internal):  # noqa: F811
    await seed(client, internal)
    near = (await client.get("/api/v1/services", params={**HERE, "sort": "distance"})).json()
    assert [s["name"] for s in near][-1] == "Haircut deluxe"
    assert near[0]["distance_km"] == pytest.approx(1.0, abs=0.3)
    assert near[-1]["distance_km"] == pytest.approx(8.9, abs=1.0)
    within = await client.get("/api/v1/services", params={**HERE, "max_km": 5})
    assert names(within) == ["Beard trim", "Haircut"]
    # Without a location there is no distance.
    assert (await client.get("/api/v1/services")).json()[0]["distance_km"] is None
    found = (await client.get("/api/v1/services/search", params={"q": "haircut", **HERE, "sort": "distance"})).json()
    assert [s["name"] for s in found] == ["Haircut", "Haircut deluxe"]


@pytest.mark.asyncio
async def test_bad_filters_are_explained(client):  # noqa: F811
    for params in (
        {"sort": "cheapest"},
        {"mode": "ONLINE"},
        {"lat": 18.5},
        {"sort": "distance"},
        {"max_km": 5},
        {"min_price": 500, "max_price": 100},
        {"min_rating": 6},
    ):
        assert (await client.get("/api/v1/services", params=params)).status_code == 422, params


@pytest.mark.asyncio
async def test_a_listing_without_facts_keeps_the_shops_location(client, internal):  # noqa: F811
    await seed(client, internal)
    # Hiding and showing a shop again (no facts sent) must not forget where it is.
    for listed in (False, True):
        await client.post("/internal/shops/shop-1/listing", json={"listed": listed}, headers=internal)
    assert names(await client.get("/api/v1/services", params={**HERE, "max_km": 5})) == ["Beard trim", "Haircut"]


def test_distance_is_the_great_circle_distance():
    # Mumbai CST to Pune station is about 120 km as the crow flies.
    assert distance_km(18.9398, 72.8355, 18.5289, 73.8744) == pytest.approx(119, abs=3)
    assert distance_km(18.5, 73.8, 18.5, 73.8) == 0
