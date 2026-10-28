"""Customers save shops to find them again: saving, listing, unsaving, and what stays hidden."""

import pytest

from app.routers import favorites
from tests import test_reviews_api
from tests.test_reviews_api import ADMIN, auth, make_shop

# The API client with an empty database (and fakes for the other services).
client = test_reviews_api.client
CUSTOMER = auth("cust-1")


def save(client, shop_id, headers=CUSTOMER):
    return client.put(f"/api/v1/shops/{shop_id}/favorite", headers=headers)


async def saved(client, headers=CUSTOMER):
    resp = await client.get("/api/v1/shops/favorites", headers=headers)
    assert resp.status_code == 200, resp.text
    return [shop["id"] for shop in resp.json()]


@pytest.mark.asyncio
async def test_a_customer_saves_shops_and_sees_the_latest_first(client):
    first = await make_shop(client, "owner-1")
    second = await make_shop(client, "owner-2")
    assert (await save(client, first)).status_code == 204
    assert (await save(client, second)).status_code == 204
    assert set(await saved(client)) == {first, second}
    assert await saved(client, auth("cust-2")) == []  # each customer has their own


@pytest.mark.asyncio
async def test_saving_twice_or_unsaving_twice_changes_nothing(client):
    shop = await make_shop(client)
    await save(client, shop)
    assert (await save(client, shop)).status_code == 204
    assert await saved(client) == [shop]
    assert (await client.delete(f"/api/v1/shops/{shop}/favorite", headers=CUSTOMER)).status_code == 204
    assert (await client.delete(f"/api/v1/shops/{shop}/favorite", headers=CUSTOMER)).status_code == 204
    assert await saved(client) == []


@pytest.mark.asyncio
async def test_the_list_hides_a_shop_that_is_no_longer_listed_and_never_shows_its_contacts(client):
    shop = await make_shop(client)
    await save(client, shop)
    [listed] = (await client.get("/api/v1/shops/favorites", headers=CUSTOMER)).json()
    assert listed["phone"] is None and listed["email"] is None

    rejected = await client.post(
        f"/api/v1/admin/shops/{shop}/reject", json={"reason": "Documents expired"}, headers=ADMIN
    )
    assert rejected.status_code == 200, rejected.text
    assert await saved(client) == []  # still saved, shown again once approved
    approved = await client.post(f"/api/v1/admin/shops/{shop}/approve", headers=ADMIN)
    assert approved.status_code == 200
    assert await saved(client) == [shop]


@pytest.mark.asyncio
async def test_an_unknown_or_unapproved_shop_cannot_be_saved(client):
    assert (await save(client, "no-such-shop")).status_code == 404
    resp = await client.post(
        "/api/v1/shops", json={"owner_id": "owner-9", "name": "New", "category": "salon"}, headers=auth("owner-9")
    )
    assert (await save(client, resp.json()["id"])).status_code == 404  # still waiting for review


@pytest.mark.asyncio
async def test_saving_needs_a_signed_in_user_and_has_a_limit(client, monkeypatch):
    shop = await make_shop(client)
    assert (await client.put(f"/api/v1/shops/{shop}/favorite")).status_code == 401
    assert (await client.get("/api/v1/shops/favorites")).status_code == 401

    monkeypatch.setattr(favorites, "MAX_FAVORITES", 1)
    other = await make_shop(client, "owner-2")
    assert (await save(client, shop)).status_code == 204
    assert (await save(client, other)).status_code == 409
    assert (await save(client, shop)).status_code == 204  # one already saved is fine


@pytest.mark.asyncio
async def test_clearing_removes_only_the_callers_saved_shops(client):
    first = await make_shop(client, "owner-1")
    second = await make_shop(client, "owner-2")
    await save(client, first)
    await save(client, second)
    await save(client, first, auth("cust-2"))
    assert (await client.delete("/api/v1/shops/favorites", headers=CUSTOMER)).status_code == 204
    assert await saved(client) == []
    assert await saved(client, auth("cust-2")) == [first]  # someone else's stay
    assert (await client.delete("/api/v1/shops/favorites", headers=CUSTOMER)).status_code == 204  # again: fine
    assert (await client.get(f"/api/v1/shops/{first}")).status_code == 200  # not taken for a shop id
