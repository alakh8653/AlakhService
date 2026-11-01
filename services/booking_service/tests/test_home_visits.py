"""Home visits: the professional's route for the day and when they reach each customer's door."""

from datetime import datetime, timedelta, timezone

import pytest

from app.core.home_visits import ARRIVED, ASSIGNED, EN_ROUTE, ON_THE_WAY, PLANNED, SERVING, Visit, plan, travel_minutes
from app.dependencies import get_location_lookup
from app.main import app
from tests import test_availability
from tests.test_availability import CLOCK, MON, book, ist, utc_iso
from tests.test_shop_bookings_api import SENT, auth

T = datetime(2030, 11, 4, 4, 30, tzinfo=timezone.utc)  # 10:00 in India
MIN = timedelta(minutes=1)
SHOP, A, B = (12.9716, 77.5946), (12.9716, 77.6406), (13.0166, 77.5946)  # B and A about 5 km from the shop


def test_travel_follows_the_distance_and_falls_back_when_a_place_is_unknown():
    assert round(travel_minutes(SHOP, A)) == 20  # ~5 km x 1.4 at 25 km/h + 3 min parking
    assert travel_minutes(SHOP, SHOP) == 5  # never less: parking, the door, the lift
    assert travel_minutes(None, A) == 20
    assert travel_minutes((12.0, 77.0), (20.0, 80.0)) == 120  # capped


def test_the_route_runs_in_order_and_an_overrun_pushes_every_later_door():
    visits = [
        Visit("later", ASSIGNED, T + 120 * MIN, 45, B),
        Visit("now", SERVING, T - 15 * MIN, 60, A, started_at=T - 15 * MIN),  # until 10:45
        Visit("next", ASSIGNED, T + 60 * MIN, 30, B),
    ]
    route = plan(visits, SHOP, T)
    now, nxt, later = route["now"], route["next"], route["later"]
    assert (now.state, now.finish_at) == (ARRIVED, T + 45 * MIN)
    # A to B is ~7 km: about 30 minutes after the 10:45 finish, so past the booked 11:00.
    assert nxt.state == PLANNED and nxt.jobs_before == 1
    assert 25 <= nxt.travel_minutes <= 35 and nxt.arrive_at == T + (45 + nxt.travel_minutes) * MIN
    assert nxt.late_minutes == nxt.travel_minutes - 15
    assert nxt.leave_at == T + 45 * MIN
    # Same building: 5 minutes, but never before the booked 12:00.
    assert (later.arrive_at, later.late_minutes, later.travel_minutes) == (T + 120 * MIN, 0, 5)
    assert later.arrive_min <= later.arrive_at <= later.arrive_max
    assert later.arrive_max - later.arrive_at > nxt.arrive_max - nxt.arrive_at  # further down, less sure

    # The job in progress runs 30 minutes over: everything after moves.
    late = plan(visits, SHOP, T + 75 * MIN)
    assert late["now"].finish_at == T + 76 * MIN
    assert late["next"].arrive_at > route["next"].arrive_at


def test_on_the_way_arrives_after_the_drive_from_when_they_left():
    route = plan([Visit("v", EN_ROUTE, T, 30, A, left_at=T - 5 * MIN)], SHOP, T)
    assert route["v"].state == ON_THE_WAY
    assert route["v"].arrive_at == T - 5 * MIN + route["v"].travel_minutes * MIN
    stuck = plan([Visit("v", EN_ROUTE, T, 30, A, left_at=T - 60 * MIN)], SHOP, T)
    assert stuck["v"].arrive_at == T + MIN  # overdue: any minute now


# The API, with test_availability's opening hours and clock.
client = test_availability.client
PLACES = {("shop", "shop-1"): SHOP, ("address", "addr-1"): A}


@pytest.fixture(autouse=True)
def places(client):
    async def lookup(kind, ref):
        return PLACES.get((kind, ref))

    app.dependency_overrides[get_location_lookup] = lambda: lookup
    SENT.clear()


@pytest.mark.asyncio
async def test_the_customer_sees_when_the_professional_will_arrive_and_hears_it_when_they_set_off(client):
    made = await book(
        client, MON, "10:00", service="svc-home", customer="hv1", service_mode="AT_HOME", address_id="addr-1"
    )
    assert made.status_code == 201, made.text
    bid = made.json()["id"]
    owner = auth("owner-1")
    assert (await client.get(f"/api/v1/bookings/{bid}/arrival", headers=auth("hv1"))).json()["state"] == "NOT_ASSIGNED"
    await client.put(f"/api/v1/bookings/{bid}/status", json={"status": "CONFIRMED"}, headers=owner)
    assert (
        await client.post(f"/api/v1/bookings/{bid}/assign", json={"provider_id": "staff-1"}, headers=owner)
    ).status_code == 200

    CLOCK["now"] = ist(MON, "09:20")
    planned = (await client.get(f"/api/v1/bookings/{bid}/arrival", headers=auth("hv1"))).json()
    assert (planned["state"], planned["arrive_at"], planned["travel_minutes"]) == ("PLANNED", utc_iso(MON, "10:00"), 20)
    route = (await client.get("/api/v1/bookings/assigned/route", headers=auth("staff-1"))).json()
    assert [(s["booking_id"], s["leave_at"]) for s in route] == [(bid, utc_iso(MON, "09:40"))]

    CLOCK["now"] = ist(MON, "09:45")  # sets off five minutes late
    moved = await client.put(
        f"/api/v1/bookings/{bid}/status", json={"status": "PROVIDER_EN_ROUTE"}, headers=auth("staff-1")
    )
    assert moved.status_code == 200, moved.text
    told = next(d for e, _, d in SENT if e == "booking.provider_en_route")
    assert told["arrival_line"] == "Arriving around 10:05 AM."
    on_way = (await client.get(f"/api/v1/bookings/{bid}/arrival", headers=auth("hv1"))).json()
    assert (on_way["state"], on_way["late_minutes"]) == ("ON_THE_WAY", 5)
    assert (await client.get(f"/api/v1/bookings/{bid}/arrival", headers=auth("stranger"))).status_code == 404


@pytest.mark.asyncio
async def test_a_visit_at_the_shop_has_no_arrival(client):
    made = await book(client, MON, "10:00", customer="hv2")
    status = (await client.get(f"/api/v1/bookings/{made.json()['id']}/arrival", headers=auth("hv2"))).json()
    assert status["state"] == "NOT_HOME_VISIT"
