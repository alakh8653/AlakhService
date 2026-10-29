"""Today's queue at a shop: place in line, people ahead, expected start and how late it runs."""

from datetime import datetime, timedelta, timezone

import pytest

from app.core import worker
from app.core.live_queue import IN_PROGRESS, WAITING_STATE, YOUR_TURN, _Visit, compute
from tests import test_availability
from tests.test_availability import CLOCK, HOURS, MON, book, ist
from tests.test_payment_sync_and_worker import PAY, Notes, fake_owner
from tests.test_shop_bookings_api import SESSIONS, auth

# The API client with test_availability's opening hours (capacity 2) and clock.
client = test_availability.client
T = datetime(2030, 11, 4, 4, 30, tzinfo=timezone.utc)  # 10:00 in India
MIN = timedelta(minutes=1)


def visit(id, status, at, minutes=30, started=None, booked_first=0):
    return _Visit(id, status, at, minutes * MIN, T - timedelta(days=1) + booked_first * MIN, started)


def test_two_places_two_being_served_and_three_waiting():
    now = T + 20 * MIN  # 10:20
    spots = compute(
        [
            visit("x", "IN_PROGRESS", T, 45, started=T),  # until 10:45
            visit("y", "IN_PROGRESS", T, 30, started=T + 5 * MIN),  # until 10:35
            visit("a", "CONFIRMED", T),
            visit("b", "CONFIRMED", T + 15 * MIN),
            visit("c", "PENDING", T + 30 * MIN),
        ],
        capacity=2,
        now=now,
    )
    assert spots["x"].state == spots["y"].state == IN_PROGRESS
    a, b, c = spots["a"], spots["b"], spots["c"]
    assert [(s.position, s.people_ahead, s.being_served) for s in (a, b, c)] == [(1, 0, 2), (2, 1, 2), (3, 2, 2)]
    assert [s.estimated_start - T for s in (a, b, c)] == [35 * MIN, 45 * MIN, 65 * MIN]
    assert [(s.wait_minutes, s.running_late_minutes) for s in (a, b, c)] == [(15, 35), (25, 30), (45, 35)]
    assert all(s.state == WAITING_STATE for s in (a, b, c))


def test_an_overrunning_service_still_holds_its_place_and_the_next_is_their_turn():
    now = T + 60 * MIN
    spots = compute(
        [visit("late", "IN_PROGRESS", T, 30, started=T), visit("next", "CONFIRMED", T + 30 * MIN)], capacity=1, now=now
    )
    assert spots["next"].estimated_start == now + MIN  # as soon as the overrun ends
    free = compute([visit("solo", "CONFIRMED", T)], capacity=1, now=T + MIN)
    assert (free["solo"].state, free["solo"].wait_minutes, free["solo"].running_late_minutes) == (YOUR_TURN, 0, 1)


def test_booking_order_breaks_ties_at_the_same_time():
    spots = compute(
        [visit("second", "CONFIRMED", T, booked_first=5), visit("first", "CONFIRMED", T, booked_first=1)],
        capacity=1,
        now=T - 30 * MIN,
    )
    assert (spots["first"].position, spots["second"].position) == (1, 2)
    assert spots["second"].estimated_start == T + 30 * MIN


async def three_waiting(client):
    """Two customers at 10:00 (the shop's two places) and one at 10:45, all confirmed, nobody started yet."""
    ids = []
    for customer, hhmm in (("q1", "10:00"), ("q2", "10:00"), ("q3", "10:45")):
        resp = await book(client, MON, hhmm, customer=customer)
        assert resp.status_code == 201, resp.text
        ids.append(resp.json()["id"])
        await client.put(f"/api/v1/bookings/{ids[-1]}/status", json={"status": "CONFIRMED"}, headers=auth("owner-1"))
    CLOCK["now"] = ist(MON, "10:50")  # the shop has not started anyone: 50 minutes behind
    return ids


@pytest.mark.asyncio
async def test_each_customer_sees_their_place_wait_and_how_late_the_shop_runs(client):
    first, _, third = await three_waiting(client)
    me = (await client.get(f"/api/v1/bookings/{third}/queue", headers=auth("q3"))).json()
    assert (me["state"], me["position"], me["people_ahead"], me["capacity"]) == ("WAITING", 3, 2, 2)
    assert (me["wait_minutes"], me["running_late_minutes"]) == (45, 50)  # after one of the 45-minute haircuts
    nxt = (await client.get(f"/api/v1/bookings/{first}/queue", headers=auth("q1"))).json()
    assert (nxt["state"], nxt["position"], nxt["wait_minutes"]) == ("YOUR_TURN", 1, 0)
    assert (await client.get(f"/api/v1/bookings/{third}/queue", headers=auth("stranger"))).status_code == 404

    shop = (await client.get("/api/v1/bookings/shop/shop-1/queue", headers=auth("owner-1"))).json()
    assert [e["position"] for e in shop] == [1, 2, 3]
    assert shop[2]["booking_id"] == third and shop[2]["running_late_minutes"] == 50
    assert (await client.get("/api/v1/bookings/shop/shop-1/queue", headers=auth("q1"))).status_code == 403


@pytest.mark.asyncio
async def test_another_day_has_no_queue_yet(client):
    resp = await book(client, MON, "10:00", customer="q9")
    CLOCK["now"] = ist(MON, "08:00") - timedelta(days=1)
    status = (await client.get(f"/api/v1/bookings/{resp.json()['id']}/queue", headers=auth("q9"))).json()
    assert (status["state"], status["position"]) == ("NOT_TODAY", None)


@pytest.mark.asyncio
async def test_customers_hear_once_that_their_turn_is_near_or_the_shop_runs_late(client):
    first, second, third = await three_waiting(client)

    async def schedule(shop_id):
        return HOURS

    notes = Notes()
    out = await worker.run_once(SESSIONS["factory"], notes, fake_owner, PAY, now=CLOCK["now"], lookup_schedule=schedule)
    sent = sorted((e, b) for e, b, _, _ in notes.sent if e in ("booking.turn_soon", "booking.running_late"))
    assert sent == sorted(
        [("booking.turn_soon", first), ("booking.turn_soon", second), ("booking.running_late", third)]
    )
    assert out["queue_notices"] == 3
    late = next(d for e, b, _, d in notes.sent if e == "booking.running_late")
    assert (late["late_minutes"], late["position"]) == (50, 3)

    notes.sent.clear()
    again = await worker.run_once(
        SESSIONS["factory"], notes, fake_owner, PAY, now=CLOCK["now"], lookup_schedule=schedule
    )
    assert again["queue_notices"] == 0
