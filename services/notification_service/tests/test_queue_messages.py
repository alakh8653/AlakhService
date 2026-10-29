"""The live queue's messages to customers, and quiet hours holding the ones that can wait."""

import pytest
from sqlalchemy import select

from app.core.events import render
from app.models.notification import Notification, NotificationPreference
from app.services.notification_service import notification_service
from tests.test_event_notifications import KEY, client  # noqa: F401

DATA = {"booking_number": "BK-9", "booking_id": "b9", "position": 3, "people_ahead": 2, "eta": "11:35 AM"}


def test_queue_messages_say_where_the_customer_stands():
    assert render("booking.queue_ahead", "customer", DATA) == (
        "You're moving up the line",
        "Booking BK-9: 2 ahead of you (#3), expected around 11:35 AM.",
    )
    assert render("booking.queue_update", "customer", {**DATA, "why": "the shop is running behind"})[1] == (
        "Booking BK-9: now expected around 11:35 AM, the shop is running behind."
    )
    assert render("booking.your_turn", "customer", {**DATA, "staff_line": "Asha is ready for you."})[1] == (
        "Booking BK-9: please go to the counter now. Asha is ready for you."
    )
    assert render("booking.your_turn", "customer", DATA)[1] == "Booking BK-9: please go to the counter now."
    assert (
        render("booking.no_show", "customer", {**DATA, "scheduled_at": "4 Nov, 10:00 AM"})[0] == "Marked as a no-show"
    )


@pytest.mark.asyncio
async def test_quiet_hours_keep_queue_updates_in_the_app_but_your_turn_still_pushes(client, monkeypatch):  # noqa: F811
    pushed = []

    async def dispatch(db, redis, channel, user_id, notif, title, body, payload):
        pushed.append(payload["event"])
        return True

    monkeypatch.setattr(notification_service, "_dispatch_channel", dispatch)
    from app.database import get_db
    from app.main import app

    async for db in app.dependency_overrides[get_db]():
        db.add(NotificationPreference(user_id="sleepy", channel="push", quiet_hours_start=0, quiet_hours_end=24))
    url = "/internal/notifications/events"
    for event in ("booking.queue_update", "booking.your_turn"):
        body = {"event": event, "recipients": [{"user_id": "sleepy", "role": "customer"}], "data": {**DATA, "why": "x"}}
        assert (await client.post(url, json=body, headers={"X-Internal-Key": KEY})).json() == {"created": 1}
    assert pushed == ["booking.your_turn"]
    async for db in app.dependency_overrides[get_db]():
        stored = (await db.execute(select(Notification.channel, Notification.title))).all()
    assert sorted(stored) == [("in_app", "New expected time"), ("push", "It's your turn")]
