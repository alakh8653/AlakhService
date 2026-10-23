"""A shop's phone and email are for its owner and admins: customers reach it through the platform."""

import pytest

from tests.test_hours_api import client  # noqa: F401  (fixture)
from tests.test_staff_api import ADMIN, OTHER, OWNER, approve


@pytest.mark.asyncio
async def test_customers_never_get_a_shops_phone_or_email(client):  # noqa: F811
    created = await client.post(
        "/api/v1/shops",
        json={
            "owner_id": "owner-1",
            "name": "Asha Salon",
            "category": "salon",
            "city": "Pune",
            "address": "12 MG Road",
            "phone": "+919876543210",
            "email": "asha@example.com",
        },
        headers=OWNER,
    )
    assert created.status_code == 201
    shop_id = created.json()["id"]
    await approve(client, shop_id)

    for headers in ({}, OTHER, {"Authorization": "Bearer not-a-token"}):
        one = (await client.get(f"/api/v1/shops/{shop_id}", headers=headers)).json()
        listed = (await client.get("/api/v1/shops", headers=headers)).json()
        found = (await client.get("/api/v1/shops/search", params={"city": "Pune"}, headers=headers)).json()
        for shop in (one, listed[0], found[0]):
            assert (shop["phone"], shop["email"]) == (None, None)
            # Directions still work: the address stays public.
            assert shop["address"] == "12 MG Road"

    for headers in (OWNER, ADMIN):
        one = (await client.get(f"/api/v1/shops/{shop_id}", headers=headers)).json()
        assert (one["phone"], one["email"]) == ("+919876543210", "asha@example.com")
