"""Customers ask for a professional when booking; the shop sees who, and still assigns the job."""

import pytest

from app.dependencies import get_team_lookup
from app.main import app
from tests import test_availability
from tests.test_availability import MON, book
from tests.test_shop_bookings_api import auth

# The API client with test_availability's opening hours and clock.
client = test_availability.client
TEAM = [
    {"id": "st-meena", "name": "Meena R.", "role": "stylist", "service_ids": ["svc-a"]},
    {"id": "st-ravi", "name": "Ravi", "role": "barber", "service_ids": ["svc-other"]},
    {"id": "st-any", "name": "Asha", "role": "stylist", "service_ids": []},
]


@pytest.fixture(autouse=True)
def team():
    async def fake_team(shop_id):
        return TEAM if shop_id == "shop-1" else []

    app.dependency_overrides[get_team_lookup] = lambda: fake_team


@pytest.mark.asyncio
async def test_the_customer_asks_for_someone_who_does_the_service(client):
    resp = await book(client, MON, "10:00", preferred_staff_id="st-meena")
    assert resp.status_code == 201, resp.text
    assert (resp.json()["preferred_staff_id"], resp.json()["preferred_staff_name"]) == ("st-meena", "Meena R.")
    shop_view = (await client.get(f"/api/v1/bookings/{resp.json()['id']}", headers=auth("owner-1"))).json()
    assert shop_view["preferred_staff_name"] == "Meena R."
    assert (await book(client, MON, "11:00", preferred_staff_id="st-any")).status_code == 201  # does every service


@pytest.mark.asyncio
async def test_someone_who_does_not_do_it_or_works_elsewhere_is_refused(client):
    assert (await book(client, MON, "10:00", preferred_staff_id="st-ravi")).status_code == 422
    assert (await book(client, MON, "10:00", preferred_staff_id="st-unknown")).status_code == 422


@pytest.mark.asyncio
async def test_without_a_preference_anyone_can_do_it(client):
    resp = await book(client, MON, "10:00")
    assert (resp.json()["preferred_staff_id"], resp.json()["preferred_staff_name"]) == (None, None)
