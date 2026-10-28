"""POST /bookings/{id}/reschedule moves a booking to another free time, within the shop's hours."""

import pytest

from app.models.booking import Booking
from tests import test_availability
from tests.test_availability import CLOCK, MON, THU, TUE, book, ist, seed, utc_iso
from tests.test_shop_bookings_api import SENT, SESSIONS, auth

# The API client with test_availability's opening hours and clock.
client = test_availability.client


def move(client, booking_id, day, hhmm, who="c5", role="user", **extra):
    body = {"scheduled_at": utc_iso(day, hhmm), **extra}
    return client.post(f"/api/v1/bookings/{booking_id}/reschedule", json=body, headers=auth(who, role))


async def booked(client, day=MON, hhmm="10:00", confirm=True) -> str:
    resp = await book(client, day, hhmm)
    assert resp.status_code == 201, resp.text
    booking_id = resp.json()["id"]
    if confirm:
        resp = await client.put(
            f"/api/v1/bookings/{booking_id}/status", json={"status": "CONFIRMED"}, headers=auth("owner-1")
        )
        assert resp.status_code == 200, resp.text
    SENT.clear()
    return booking_id


async def stored(booking_id) -> Booking:
    async with SESSIONS["factory"]() as db:
        return await db.get(Booking, booking_id)


@pytest.mark.asyncio
async def test_the_customer_moves_a_confirmed_booking_and_the_shop_is_told(client):
    booking_id = await booked(client)
    async with SESSIONS["factory"]() as db:
        row = await db.get(Booking, booking_id)
        row.reminder_24h_sent_at = ist(MON, "08:00")
        await db.commit()

    resp = await move(client, booking_id, TUE, "15:30", reason="Stuck at work")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert (body["status"], body["reschedule_count"]) == ("CONFIRMED", 1)
    assert body["scheduled_at"].startswith(utc_iso(TUE, "15:30")[:16])

    row = await stored(booking_id)
    assert row.reminder_24h_sent_at is None  # the reminders follow the new time
    history = (await client.get(f"/api/v1/bookings/{booking_id}/history", headers=auth("c5"))).json()
    assert history[-1]["from_status"] == history[-1]["to_status"] == "CONFIRMED"
    assert "Rescheduled from" in history[-1]["reason"] and "Stuck at work" in history[-1]["reason"]

    [(event, recipients, data)] = SENT
    assert (event, recipients) == ("booking.rescheduled", [("owner-1", "shop")])
    assert data["previous_scheduled_at"] == "04 Nov, 10:00 AM"
    assert data["scheduled_at"] == "05 Nov, 03:30 PM"


@pytest.mark.asyncio
async def test_a_time_the_shop_is_closed_or_full_is_refused_and_nothing_changes(client):
    booking_id = await booked(client)
    closed = await move(client, booking_id, THU, "11:00")  # closed on Thursdays
    assert closed.status_code == 409

    await seed(("shop-1", TUE, "11:00", 60, "CONFIRMED"), ("shop-1", TUE, "11:00", 60, "CONFIRMED"))
    full = await move(client, booking_id, TUE, "11:15")  # both places taken
    assert full.status_code == 409

    row = await stored(booking_id)
    assert (row.reschedule_count, SENT) == (0, [])
    assert utc_iso(MON, "10:00").startswith(row.scheduled_at.strftime("%Y-%m-%dT%H:%M"))


@pytest.mark.asyncio
async def test_a_booking_does_not_compete_with_its_own_old_time(client):
    booking_id = await booked(client)
    # One of the two places is taken by someone else; the other is this booking's own.
    await seed(("shop-1", MON, "10:00", 60, "CONFIRMED"))
    resp = await move(client, booking_id, MON, "10:15")
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_the_customer_cannot_move_it_at_the_last_minute_but_the_shop_can(client):
    booking_id = await booked(client)
    CLOCK["now"] = ist(MON, "08:30")  # 90 minutes before the start
    late = await move(client, booking_id, MON, "17:00")
    assert late.status_code == 409 and "2 hours" in late.json()["detail"]

    resp = await move(client, booking_id, MON, "17:00", who="owner-1")
    assert resp.status_code == 200, resp.text
    assert resp.json()["reschedule_count"] == 0  # the shop's moves do not use up the customer's
    [(event, recipients, _)] = SENT
    assert (event, recipients) == ("booking.rescheduled", [("c5", "customer")])


@pytest.mark.asyncio
async def test_the_customer_can_move_a_booking_only_twice(client):
    booking_id = await booked(client)
    assert (await move(client, booking_id, TUE, "10:00")).status_code == 200
    assert (await move(client, booking_id, TUE, "12:00")).status_code == 200
    third = await move(client, booking_id, TUE, "14:00")
    assert third.status_code == 409 and "Cancel it" in third.json()["detail"]
    # An admin can still help.
    assert (await move(client, booking_id, TUE, "14:00", who="admin-1", role="admin")).status_code == 200


@pytest.mark.asyncio
async def test_a_pending_booking_can_be_moved_but_not_one_a_provider_has(client):
    pending = await booked(client, confirm=False)
    assert (await move(client, pending, TUE, "10:00")).status_code == 200

    assigned = await booked(client, MON, "12:00")
    resp = await client.post(
        f"/api/v1/bookings/{assigned}/assign", json={"provider_id": "staff-1"}, headers=auth("owner-1")
    )
    assert resp.status_code == 200, resp.text
    refused = await move(client, assigned, TUE, "12:00")
    assert refused.status_code == 409


@pytest.mark.asyncio
async def test_only_the_people_on_the_booking_may_move_it(client):
    booking_id = await booked(client)
    assert (await move(client, booking_id, TUE, "10:00", who="stranger")).status_code == 404
    assert (await move(client, booking_id, TUE, "10:00", who="owner-2")).status_code == 404
    same = await move(client, booking_id, MON, "10:00")
    assert same.status_code == 422


@pytest.mark.asyncio
async def test_a_time_in_the_past_is_rejected(client):
    booking_id = await booked(client)
    resp = await client.post(
        f"/api/v1/bookings/{booking_id}/reschedule",
        json={"scheduled_at": "2020-01-01T10:00:00Z"},
        headers=auth("c5"),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_the_time_picker_counts_the_moved_booking_as_free_to_itself(client):
    booking_id = await booked(client)
    await seed(("shop-1", MON, "10:00", 60, "CONFIRMED"))  # both places at 10:00 are now taken
    params = {"service_id": "svc-a", "date": MON.isoformat()}
    plain = (await client.get("/api/v1/availability", params=params)).json()
    moving = (await client.get("/api/v1/availability", params={**params, "moving_booking_id": booking_id})).json()
    assert "10:15" not in [s["time"] for s in plain["slots"]]
    assert "10:15" in [s["time"] for s in moving["slots"]]
