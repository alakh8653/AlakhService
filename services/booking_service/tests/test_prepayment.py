"""A shop that asks customers to pay online when they book: the booking holds its place briefly, is
confirmed once paid (at a shop that confirms on its own) and released if not paid in time."""

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.config import settings
from app.core import worker
from app.main import app
from app.models.booking import Booking
from tests.test_availability import CLOCK, HOURS, MON, book, client, slots  # noqa: F401  (client is a fixture)
from tests.test_payment_sync_and_worker import PAY, Notes, fake_owner
from tests.test_shop_bookings_api import SCHEDULES, SENT, SESSIONS

KEY = "k" * 40
INTERNAL = {"X-Internal-Key": KEY}


@pytest.fixture(autouse=True)
def internal_key(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", KEY)
    from app.core.payments import get_payment_client

    app.dependency_overrides[get_payment_client] = lambda: PAY
    PAY.sent.clear()


async def stored(booking_id):
    async with SESSIONS["factory"]() as db:
        return await db.get(Booking, booking_id)


@pytest.mark.asyncio
async def test_a_booking_waits_for_payment_and_is_confirmed_once_paid(client):  # noqa: F811
    SCHEDULES["shop-1"] = {**HOURS, "capacity": 1, "auto_confirm": True, "require_prepayment": True}
    made = (await book(client, MON, "10:00")).json()
    # Not confirmed yet, though the shop confirms on its own: it is held for payment.
    assert made["status"] == "PENDING"
    due = made["payment_due_at"]
    assert due is not None
    # The place is held meanwhile.
    assert (await book(client, MON, "10:00", customer="c6")).status_code == 409

    SENT.clear()
    paid = await client.post(
        f"/internal/bookings/{made['id']}/payment-status", json={"payment_status": "PAID"}, headers=INTERNAL
    )
    assert paid.status_code == 200
    after = await stored(made["id"])
    assert (after.status, after.payment_due_at) == ("CONFIRMED", None)
    assert [e for e, *_ in SENT if e == "booking.confirmed"] == ["booking.confirmed"]


@pytest.mark.asyncio
async def test_an_unpaid_booking_is_released_after_the_window(client):  # noqa: F811
    SCHEDULES["shop-1"] = {**HOURS, "capacity": 1, "require_prepayment": True}
    made = (await book(client, MON, "10:00")).json()
    # Made now by the test clock (the 12-hour "shop never confirmed" rule goes by when it was made).
    async with SESSIONS["factory"]() as db:
        (await db.get(Booking, made["id"])).created_at = CLOCK["now"]
        await db.commit()
    notes = Notes()
    # Still inside the window: nothing happens.
    out = await worker.run_once(SESSIONS["factory"], notes, fake_owner, PAY, now=CLOCK["now"] + timedelta(minutes=10))
    assert out["released_unpaid"] == 0
    out = await worker.run_once(
        SESSIONS["factory"],
        notes,
        fake_owner,
        PAY,
        now=CLOCK["now"] + timedelta(minutes=settings.PREPAY_WINDOW_MINUTES + 1),
    )
    assert out["released_unpaid"] == 1
    gone = await stored(made["id"])
    assert (gone.status, gone.cancellation_reason) == ("CANCELLED", "Not paid in time")
    told = [
        (b, roles, d["reason"])
        for e, b, roles, d in notes.sent
        if e == "booking.expired" and d["reason"] == "Not paid in time"
    ]
    assert told == [(made["id"], ("customer", "shop"), "Not paid in time")]
    # The place is free again.
    assert (await book(client, MON, "10:00", customer="c6")).status_code == 201


@pytest.mark.asyncio
async def test_a_paid_booking_is_never_released(client):  # noqa: F811
    SCHEDULES["shop-1"] = {**HOURS, "capacity": 1, "require_prepayment": True}
    made = (await book(client, MON, "10:00")).json()
    await client.post(
        f"/internal/bookings/{made['id']}/payment-status", json={"payment_status": "PAID"}, headers=INTERNAL
    )
    # Without auto-confirm the shop still accepts it itself, but nothing releases it.
    assert (await stored(made["id"])).status == "PENDING"
    out = await worker.run_once(SESSIONS["factory"], Notes(), fake_owner, PAY, now=CLOCK["now"] + timedelta(hours=1))
    assert out["released_unpaid"] == 0
    assert (await stored(made["id"])).payment_due_at is None


@pytest.mark.asyncio
async def test_shops_that_do_not_ask_for_payment_are_unchanged(client):  # noqa: F811
    SCHEDULES["shop-1"] = {**HOURS, "capacity": 1, "auto_confirm": True}
    made = (await book(client, MON, "10:00")).json()
    assert (made["status"], made["payment_due_at"]) == ("CONFIRMED", None)
    async with SESSIONS["factory"]() as db:
        assert (await db.execute(select(Booking.payment_due_at))).scalars().all() == [None] * len(
            (await db.execute(select(Booking.id))).scalars().all()
        )


@pytest.mark.asyncio
async def test_a_booking_for_someone_else_tells_the_shop_who_to_expect(client):  # noqa: F811
    SCHEDULES["shop-1"] = {**HOURS, "capacity": 2}
    made = await book(client, MON, "10:00", guest_name="  Asha   Rao ")
    assert made.status_code == 201
    assert made.json()["guest_name"] == "Asha Rao"
    # A number is never passed on this way.
    refused = await book(client, MON, "11:00", guest_name="call 98765 43210")
    assert refused.status_code == 422
    # Without a guest the booking is as before.
    assert (await book(client, MON, "12:00")).json()["guest_name"] is None
