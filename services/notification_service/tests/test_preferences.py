"""Customers choose how they are told: push, SMS and email can each be switched off, and quiet hours hold
updates that can wait. The app's own list always keeps every notice."""

from datetime import datetime, timezone

import pytest

from app.services.notification_service import notification_service
from tests.test_event_notifications import auth
from tests.test_fallbacks import client, notify  # noqa: F401  (client is a fixture)

URL = "/api/v1/notifications/preferences"


@pytest.mark.asyncio
async def test_everything_is_on_until_changed_and_each_person_has_their_own(client):  # noqa: F811
    assert (await client.get(URL, headers=auth("cust"))).json() == {
        "push": True,
        "sms": True,
        "email": True,
        "quiet_hours": None,
    }
    saved = await client.put(
        URL,
        json={"push": True, "sms": False, "email": True, "quiet_hours": {"start": 22, "end": 7}},
        headers=auth("cust"),
    )
    assert saved.json() == {"push": True, "sms": False, "email": True, "quiet_hours": {"start": 22, "end": 7}}
    assert (await client.get(URL, headers=auth("cust"))).json()["sms"] is False
    assert (await client.get(URL, headers=auth("someone-else"))).json()["sms"] is True
    assert (await client.get(URL)).status_code == 401
    assert (
        await client.put(URL, json={"quiet_hours": {"start": 25, "end": 7}}, headers=auth("cust"))
    ).status_code == 422


@pytest.mark.asyncio
async def test_switching_sms_off_stops_the_texts_but_email_can_still_reach_them(client):  # noqa: F811
    await client.put(URL, json={"push": True, "sms": False, "email": True}, headers=auth("cust"))
    await notify(client, "booking.confirmed", [{"user_id": "cust", "role": "customer"}])
    assert [kind for kind, *_ in client.sent] == ["email"]


@pytest.mark.asyncio
async def test_with_sms_and_email_off_nothing_leaves_the_app(client):  # noqa: F811
    await client.put(URL, json={"push": True, "sms": False, "email": False}, headers=auth("cust"))
    created = await notify(client, "booking.confirmed", [{"user_id": "cust", "role": "customer"}])
    assert created == {"created": 1}  # still in the app's list
    assert client.sent == []


@pytest.mark.asyncio
async def test_quiet_hours_are_the_persons_own_clock_hours(client):  # noqa: F811
    await client.put(URL, json={"quiet_hours": {"start": 22, "end": 7}}, headers=auth("cust"))
    async with client.factory() as db:
        # 17:00 UTC is 22:30 in India: quiet. 03:00 UTC is 08:30 in India: not.
        assert await notification_service.check_quiet_hours(
            db, "cust", datetime(2026, 11, 28, 17, 0, tzinfo=timezone.utc)
        )
        assert not await notification_service.check_quiet_hours(
            db, "cust", datetime(2026, 11, 28, 3, 0, tzinfo=timezone.utc)
        )
