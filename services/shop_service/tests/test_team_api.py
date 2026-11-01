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
    assert all(set(m) == {"id", "name", "role", "service_ids", "working_hours"} for m in team)  # no phone or email


@pytest.mark.asyncio
async def test_a_shop_not_listed_yet_shows_no_team(client):
    pending = await make_shop(client, owner="owner-2", name="New", approved=False)
    assert (await client.get(f"/api/v1/shops/{pending['id']}/team")).status_code == 404
    assert (await client.get("/api/v1/shops/nope/team")).status_code == 404


@pytest.mark.asyncio
async def test_each_team_member_can_have_their_own_week(client):
    shop = await make_shop(client)
    week = [
        # Saturday given before Monday, Monday as a split shift: stored Monday first.
        {"day": 5, "intervals": [{"start": "10:00", "end": "16:00"}]},
        {"day": 0, "intervals": [{"start": "15:00", "end": "19:00"}, {"start": "09:00", "end": "12:00"}]},
    ]
    made = await client.post(
        "/api/v1/staff", json={"shop_id": shop["id"], "name": "Asha", "working_hours": week}, headers=OWNER
    )
    assert made.status_code == 201, made.text
    expected = [
        {"day": 0, "intervals": [{"start": "09:00", "end": "12:00"}, {"start": "15:00", "end": "19:00"}]},
        {"day": 5, "intervals": [{"start": "10:00", "end": "16:00"}]},
    ]
    assert made.json()["working_hours"] == expected
    other = await client.post("/api/v1/staff", json={"shop_id": shop["id"], "name": "Ravi"}, headers=OWNER)
    assert other.json()["working_hours"] is None  # the shop's hours

    team = {m["name"]: m for m in (await client.get(f"/api/v1/shops/{shop['id']}/team")).json()}
    assert team["Asha"]["working_hours"] == expected
    assert team["Ravi"]["working_hours"] is None

    staff_id = made.json()["id"]
    changed = await client.put(f"/api/v1/staff/{staff_id}", json={"role": "senior"}, headers=OWNER)
    assert changed.json()["working_hours"] == expected  # untouched when not sent
    back = await client.put(f"/api/v1/staff/{staff_id}", json={"working_hours": None}, headers=OWNER)
    assert back.json()["working_hours"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "week",
    [
        [{"day": 0, "intervals": [{"start": "09:00", "end": "12:00"}]}, {"day": 0, "intervals": []}],
        [{"day": 7, "intervals": []}],
        [{"day": 1, "intervals": [{"start": "12:00", "end": "09:00"}]}],
        [{"day": 1, "intervals": [{"start": "09:00", "end": "12:00"}, {"start": "11:00", "end": "13:00"}]}],
        [{"day": 1, "intervals": [{"start": "09:10", "end": "12:00"}]}],
    ],
)
async def test_a_week_that_makes_no_sense_is_refused(client, week):
    shop = await make_shop(client)
    resp = await client.post(
        "/api/v1/staff", json={"shop_id": shop["id"], "name": "Asha", "working_hours": week}, headers=OWNER
    )
    assert resp.status_code == 422
