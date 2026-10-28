"""Customers see a listed shop's team, to ask for someone when booking, without their contact details."""

import pytest

from tests import test_staff_api
from tests.test_staff_api import OWNER, make_shop

# The API client with an empty database (see test_staff_api).
client = test_staff_api.client


@pytest.mark.asyncio
async def test_the_team_shows_active_staff_by_first_name_and_what_they_do(client):
    shop = await make_shop(client)
    for body in (
        {"name": "Meena Kumari Rao", "role": "stylist", "service_ids": ["svc-cut"], "phone": "+919999999999"},
        {"name": "Ravi", "role": "barber"},
        {"name": "Gone Person", "role": "stylist"},
    ):
        resp = await client.post("/api/v1/staff", json={"shop_id": shop["id"], **body}, headers=OWNER)
        assert resp.status_code == 201
    gone = resp.json()["id"]
    await client.put(f"/api/v1/staff/{gone}", json={"is_active": False}, headers=OWNER)

    team = (await client.get(f"/api/v1/shops/{shop['id']}/team")).json()  # no sign-in needed
    assert sorted((m["name"], m["role"], m["service_ids"]) for m in team) == [
        ("Meena R.", "stylist", ["svc-cut"]),
        ("Ravi", "barber", []),
    ]
    assert all(set(m) == {"id", "name", "role", "service_ids"} for m in team)  # no phone or email


@pytest.mark.asyncio
async def test_a_shop_not_listed_yet_shows_no_team(client):
    pending = await make_shop(client, owner="owner-2", name="New", approved=False)
    assert (await client.get(f"/api/v1/shops/{pending['id']}/team")).status_code == 404
    assert (await client.get("/api/v1/shops/nope/team")).status_code == 404
