"""A shop is removed: what has not started is cancelled and refunded, and customers are told."""

import pytest
from sqlalchemy import update

from app import dependencies
from app.models.booking import Booking
from tests.test_payment_sync_and_worker import INTERNAL, PAY, http, outbox, stored  # noqa: F401
from tests.test_shop_bookings_api import SENT, SESSIONS

URL = "/internal/bookings/shops/shop-1/cancel-upcoming"


async def set_status(booking_id, status):
    async with SESSIONS["factory"]() as db:
        await db.execute(update(Booking).where(Booking.id == booking_id).values(status=status))
        await db.commit()


@pytest.mark.asyncio
async def test_what_has_not_started_is_cancelled_refunded_and_the_customer_told(http):  # noqa: F811
    await set_status("bk-3", "CONFIRMED")
    SENT.clear()
    resp = await http.post(URL, headers=INTERNAL)
    assert (resp.status_code, resp.json()["cancelled"]) == (200, 2)

    for booking_id in ("bk-3", "bk-4"):
        booking = await stored(booking_id)
        assert booking.status == "CANCELLED"
        assert booking.cancellation_reason == "The shop is no longer on AlakhService"
    assert sorted((b, k, p["cancelled_by"]) for b, k, p in PAY.sent) == [
        ("bk-3", "cancelled", "shop"),
        ("bk-4", "cancelled", "shop"),
    ]
    told = {person for event, people, _ in SENT if event == "booking.cancelled" for person in people}
    assert {("c1", "customer"), ("c3", "customer")} <= told
    assert "shop" not in {role for _, role in told}
    # Finished bookings and other shops' are left alone.
    assert (await stored("bk-1")).status == "COMPLETED"
    assert (await stored("bk-6")).status == "COMPLETED"


@pytest.mark.asyncio
async def test_repeating_it_cancels_and_refunds_nothing_more(http):  # noqa: F811
    assert (await http.post(URL, headers=INTERNAL)).json()["cancelled"] == 1
    assert (await http.post(URL, headers=INTERNAL)).json()["cancelled"] == 0
    assert len(await outbox()) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["PROVIDER_EN_ROUTE", "PICKED_UP", "IN_PROGRESS", "OUT_FOR_DELIVERY"])
async def test_it_is_refused_and_changes_nothing_while_a_booking_is_being_served(http, status):  # noqa: F811
    await set_status("bk-3", status)
    resp = await http.post(URL, headers=INTERNAL)
    assert resp.status_code == 409
    assert "being served" in resp.json()["detail"]
    assert (await stored("bk-4")).status == "PENDING"
    assert await outbox() == []


@pytest.mark.asyncio
async def test_new_bookings_see_the_shop_closed_at_once(http, monkeypatch):  # noqa: F811
    dependencies._schedule_cache.put("shop-1", {"accepting_bookings": True})
    assert (await http.post(URL, headers=INTERNAL)).status_code == 200
    assert dependencies._schedule_cache.fresh("shop-1") == (False, None)


@pytest.mark.asyncio
async def test_only_other_services_may_ask(http):  # noqa: F811
    assert (await http.post(URL)).status_code in (401, 403)
    assert (await stored("bk-4")).status == "PENDING"
