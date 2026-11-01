"""Customers wait for a full day at a shop and are told once when a time there opens up."""

import pytest

from app.core import waitlist
from tests import test_availability
from tests.test_availability import MON, TUE, book, utc_iso
from tests.test_shop_bookings_api import SENT, auth

# The API client with test_availability's opening hours and clock.
client = test_availability.client


def join(client, day, who="w1", service="svc-a"):
    return client.post("/api/v1/waitlist", json={"service_id": service, "date": day.isoformat()}, headers=auth(who))


def told():
    return sorted(r[0][0] for e, r, _ in SENT if e == "waitlist.time_opened")


@pytest.mark.asyncio
async def test_customers_join_list_and_leave_the_waitlist(client):
    first = await join(client, MON)
    assert first.status_code == 201, first.text
    assert (first.json()["date"], first.json()["shop_id"]) == (MON.isoformat(), "shop-1")
    assert (await join(client, MON)).json()["id"] == first.json()["id"]  # joining twice: one entry
    mine = (await client.get("/api/v1/waitlist", headers=auth("w1"))).json()
    assert [e["date"] for e in mine] == [MON.isoformat()]
    assert (await client.delete(f"/api/v1/waitlist/{first.json()['id']}", headers=auth("other"))).status_code == 404
    assert (await client.delete(f"/api/v1/waitlist/{first.json()['id']}", headers=auth("w1"))).status_code == 204
    assert (await client.get("/api/v1/waitlist", headers=auth("w1"))).json() == []
    assert (await join(client, MON, service="no-such")).status_code == 404
    assert (
        await client.post("/api/v1/waitlist", json={"service_id": "svc-a", "date": "2020-01-01"}, headers=auth("w1"))
    ).status_code == 422


@pytest.mark.asyncio
async def test_a_cancel_tells_everyone_waiting_for_that_day_once(client):
    booked = (await book(client, MON, "10:00")).json()
    await join(client, MON, "w1")
    await join(client, MON, "w2")
    await join(client, TUE, "w3")  # another day
    await join(client, MON, "c5")  # the customer who cancels is not told about their own time
    SENT.clear()
    resp = await client.post(
        f"/api/v1/bookings/{booked['id']}/cancel", json={"reason": "Plans changed"}, headers=auth("c5")
    )
    assert resp.status_code == 200, resp.text
    assert told() == ["w1", "w2"]
    [(_, _, data)] = [s for s in SENT if s[0] == "waitlist.time_opened"][:1]
    assert data["shop_id"] == "shop-1" and data["service_id"] == "svc-a"

    # Told once: another cancellation that day tells nobody new.
    other = (await book(client, MON, "11:00", customer="c6")).json()
    SENT.clear()
    await client.post(f"/api/v1/bookings/{other['id']}/cancel", json={"reason": "x"}, headers=auth("c6"))
    assert told() == ["c5"]  # still waiting from before; the others were told already


@pytest.mark.asyncio
async def test_moving_a_booking_to_another_day_frees_the_old_one(client):
    booked = (await book(client, MON, "10:00")).json()
    await client.put(f"/api/v1/bookings/{booked['id']}/status", json={"status": "CONFIRMED"}, headers=auth("owner-1"))
    await join(client, MON, "w1")
    await join(client, TUE, "w2")
    SENT.clear()
    same_day = await client.post(
        f"/api/v1/bookings/{booked['id']}/reschedule", json={"scheduled_at": utc_iso(MON, "12:00")}, headers=auth("c5")
    )
    assert same_day.status_code == 200 and told() == []  # the day is no freer than before
    moved = await client.post(
        f"/api/v1/bookings/{booked['id']}/reschedule", json={"scheduled_at": utc_iso(TUE, "12:00")}, headers=auth("c5")
    )
    assert moved.status_code == 200 and told() == ["w1"]


@pytest.mark.asyncio
async def test_one_customer_waits_for_a_few_days_at_most(client, monkeypatch):
    monkeypatch.setattr(waitlist, "MAX_WAITING", 1)
    assert (await join(client, MON)).status_code == 201
    assert (await join(client, TUE)).status_code == 422
