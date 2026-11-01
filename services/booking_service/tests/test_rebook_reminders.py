"""Some weeks after a completed visit the customer is asked once whether to book it again."""

from datetime import timedelta

import pytest

from app.core import worker
from tests import test_payment_sync_and_worker
from tests.test_payment_sync_and_worker import NOW, PAY, Notes, fake_owner, new_booking, stored
from tests.test_shop_bookings_api import SESSIONS

# The API client and fakes from the worker tests.
http = test_payment_sync_and_worker.http
DAY = timedelta(days=1)


@pytest.mark.asyncio
async def test_a_completed_visit_is_followed_up_once_unless_already_rebooked(http):
    async with SESSIONS["factory"]() as db:
        db.add_all(
            [
                new_booking(1, "COMPLETED", NOW - 30 * DAY),  # due
                new_booking(2, "COMPLETED", NOW - 30 * DAY, customer="loyal"),  # booked again since
                new_booking(3, "CONFIRMED", NOW + 2 * DAY, customer="loyal"),
                new_booking(4, "COMPLETED", NOW - 10 * DAY, customer="recent"),  # too soon
                new_booking(5, "COMPLETED", NOW - 90 * DAY, customer="long-ago"),  # before this was switched on
                new_booking(6, "CANCELLED", NOW - 30 * DAY, customer="cancelled"),  # never happened
                new_booking(7, "COMPLETED", NOW - 31 * DAY, customer="came-back-cancelled"),  # rebooked, then cancelled
                new_booking(8, "CANCELLED", NOW + 3 * DAY, customer="came-back-cancelled"),
            ]
        )
        await db.commit()
    notes = Notes()
    out = await worker.run_once(SESSIONS["factory"], notes, fake_owner, PAY, now=NOW)
    # Only this test's visits (w-*): the shared fixture also seeds bookings with fixed dates.
    asked = sorted(b for e, b, _, _ in notes.sent if e == "booking.rebook" and b.startswith("w-"))
    assert asked == ["w-1", "w-7"]
    assert out["rebook_reminders"] >= 2
    assert all(roles == ("customer",) for e, _, roles, _ in notes.sent if e == "booking.rebook")
    assert (await stored("w-2")).rebook_reminder_sent_at is not None  # considered, so never asked later

    notes.sent.clear()
    await worker.run_once(SESSIONS["factory"], notes, fake_owner, PAY, now=NOW + DAY)
    assert not [b for e, b, *_ in notes.sent if e == "booking.rebook" and b.startswith("w-")]


@pytest.mark.asyncio
async def test_rebook_reminders_can_be_switched_off(http, monkeypatch):
    monkeypatch.setattr(worker.settings, "REBOOK_REMINDER_DAYS", 0)
    async with SESSIONS["factory"]() as db:
        db.add(new_booking(1, "COMPLETED", NOW - 30 * DAY))
        await db.commit()
    out = await worker.run_once(SESSIONS["factory"], Notes(), fake_owner, PAY, now=NOW)
    assert out["rebook_reminders"] == 0
