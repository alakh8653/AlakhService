"""People without the app still hear about critical booking events, by SMS or email; shop owners get
new bookings by email; MSG91 texts with DLT templates; nobody's contact details leak into a message."""

import json

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models.notification  # noqa: F401
from app.channels.msg91 import MSG91SMSChannel
from app.config import settings
from app.core import contact as contact_module
from app.core.events import render, render_sms
from app.database import Base, get_db
from app.main import app
from app.models.notification import DeviceToken
from app.routers.notifications import get_redis
from app.services import notification_service as service_module
from app.services.notification_service import notification_service

KEY = "internal-test-key"
CONTACTS = {
    "cust": {"phone": "+919876543210", "email": "cust@example.com"},
    "mail-only": {"phone": None, "email": "mail@example.com"},
    "owner": {"phone": "+919812345678", "email": "owner@example.com"},
}


class FakeRedis:
    async def publish(self, channel, payload):
        return 1


@pytest_asyncio.fixture
async def client(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", KEY)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            yield session
            await session.commit()

    async def override_redis():
        yield FakeRedis()

    sent = []

    async def fake_contact(user_id, transport=None):
        return CONTACTS.get(user_id)

    async def fake_sms(to, body, event):
        sent.append(("sms", to, body, event))
        return True

    async def fake_email(to, subject, body):
        sent.append(("email", to, subject, body))
        return True

    async def fake_push(*args):
        return True

    monkeypatch.setattr(service_module, "fetch_contact", fake_contact)
    monkeypatch.setattr(notification_service, "send_sms", fake_sms)
    monkeypatch.setattr(notification_service, "send_email", fake_email)
    monkeypatch.setattr(notification_service, "_get_fcm", lambda: type("F", (), {"send": staticmethod(fake_push)})())
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_redis
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        ac.sent, ac.factory = sent, factory
        yield ac
    app.dependency_overrides.clear()
    await engine.dispose()


DATA = {"booking_id": "b1", "booking_number": "BK-7", "scheduled_at": "24 Oct, 10:30 AM", "service_name": "Haircut"}


async def notify(client, event, recipients, data=DATA):
    resp = await client.post(
        "/internal/notifications/events",
        json={"event": event, "recipients": recipients, "data": data},
        headers={"X-Internal-Key": KEY},
    )
    assert resp.status_code == 200
    return resp.json()


@pytest.mark.asyncio
async def test_critical_events_are_texted_to_people_without_the_app(client):
    await notify(client, "booking.confirmed", [{"user_id": "cust", "role": "customer"}])
    assert client.sent == [
        (
            "sms",
            "+919876543210",
            "AlakhService: booking BK-7 for 24 Oct, 10:30 AM is confirmed. Details in the app.",
            "booking.confirmed",
        )
    ]


@pytest.mark.asyncio
async def test_without_a_phone_or_a_text_the_fallback_is_email(client, monkeypatch):
    await notify(client, "booking.reminder", [{"user_id": "mail-only", "role": "customer"}])
    [(channel, to, subject, body)] = client.sent
    assert (channel, to, subject) == ("email", "mail@example.com", "AlakhService: Booking reminder")
    assert body.startswith("Reminder: your Haircut booking BK-7 is at 24 Oct, 10:30 AM.")

    client.sent.clear()

    async def sms_fails(to, body, event):
        return False

    monkeypatch.setattr(notification_service, "send_sms", sms_fails)
    await notify(client, "booking.expired", [{"user_id": "cust", "role": "customer"}])
    assert [(c, to) for c, to, *_ in client.sent] == [("email", "cust@example.com")]


@pytest.mark.asyncio
async def test_people_with_the_app_and_minor_events_get_no_sms(client):
    async with client.factory() as db:
        db.add(DeviceToken(user_id="cust", token="device-1", platform="android"))
        await db.commit()
    await notify(client, "booking.cancelled", [{"user_id": "cust", "role": "customer"}])
    await notify(client, "booking.in_progress", [{"user_id": "mail-only", "role": "customer"}])
    # Unknown or deleted accounts are simply skipped.
    await notify(client, "booking.confirmed", [{"user_id": "gone", "role": "customer"}])
    assert client.sent == []


@pytest.mark.asyncio
async def test_shop_owners_get_new_bookings_by_email(client, monkeypatch):
    monkeypatch.setattr(settings, "SHOP_DASHBOARD_URL", "https://shop.alakh.example.in")
    await notify(client, "booking.created", [{"user_id": "owner", "role": "shop"}])
    [(channel, to, subject, body)] = client.sent
    assert (channel, to, subject) == ("email", "owner@example.com", "AlakhService: New booking")
    assert "Haircut booked for 24 Oct, 10:30 AM. Booking BK-7." in body
    assert "https://shop.alakh.example.in" in body
    # Never the customer's contact details.
    assert "9876543210" not in body and "cust@example.com" not in body


def test_reminder_and_expiry_wording():
    assert render("booking.reminder", "shop", DATA) == (
        "Upcoming booking",
        "Reminder: booking BK-7 for Haircut is at 24 Oct, 10:30 AM.",
    )
    title, body = render("booking.expired", "customer", DATA)
    assert title == "Booking request expired" and "refunded in 5-7 working days" in body
    assert render("booking.expired", "shop", DATA)[1] == (
        "Booking BK-7 for 24 Oct, 10:30 AM expired because it was not confirmed in time."
    )
    assert render_sms("booking.reminder", DATA) == "AlakhService reminder: booking BK-7 is at 24 Oct, 10:30 AM."
    assert render_sms("booking.created", DATA) is None


def test_contact_details_never_reach_a_message():
    leaky = {**DATA, "service_name": "Haircut call 98765 43210 or +91-9876543210 or me@example.com"}
    _, body = render("booking.reminder", "customer", leaky)
    assert "98765" not in body and "9876543210" not in body and "@" not in body
    assert "BK-7" in body  # booking numbers survive
    assert "9876543210" not in render_sms("booking.confirmed", {**DATA, "booking_number": "9876543210"})


@pytest.mark.asyncio
async def test_msg91_texts_with_the_events_dlt_template(monkeypatch):
    calls = []

    def msg91(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"type": "success", "message": "ok"})

    channel = MSG91SMSChannel("auth-key", "ALAKHS", transport=httpx.MockTransport(msg91))
    assert await channel.send("+919876543210", "AlakhService: hi", "1107000000000000001")
    assert calls[0].headers["authkey"] == "auth-key"
    assert json.loads(calls[0].content) == {
        "sender": "ALAKHS",
        "route": "4",
        "country": "91",
        "DLT_TE_ID": "1107000000000000001",
        "sms": [{"message": "AlakhService: hi", "to": ["919876543210"]}],
    }
    # No template id: not sent (DLT would reject it anyway).
    assert not await channel.send("+919876543210", "x", "")
    assert len(calls) == 1
    refused = MSG91SMSChannel(
        "k", "S", transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"type": "error"}))
    )
    assert not await refused.send("+919876543210", "x", "t")

    # The service picks the template for each event from its own setting.
    sent = []

    class FakeMSG91:
        async def send(self, to, body, template_id):
            sent.append(template_id)
            return True

    monkeypatch.setattr(settings, "SMS_PROVIDER", "msg91")
    monkeypatch.setattr(settings, "MSG91_TEMPLATE_BOOKING_EXPIRED", "1107-expired")
    monkeypatch.setattr(notification_service, "_get_msg91", lambda: FakeMSG91())
    assert await notification_service.send_sms("+919876543210", "x", "booking.expired")
    assert sent == ["1107-expired"]
    monkeypatch.setattr(settings, "SMS_PROVIDER", "none")
    assert not await notification_service.send_sms("+919876543210", "x", "booking.expired")


@pytest.mark.asyncio
async def test_contact_lookup_uses_the_internal_key(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", KEY)
    seen = []

    def auth(request: httpx.Request) -> httpx.Response:
        seen.append((request.url.path, request.headers["x-internal-key"]))
        if "missing" in request.url.path:
            return httpx.Response(404, json={"detail": "User not found"})
        return httpx.Response(200, json={"phone": "+919876543210", "email": None})

    transport = httpx.MockTransport(auth)
    assert await contact_module.fetch_contact("u1", transport=transport) == {"phone": "+919876543210", "email": None}
    assert await contact_module.fetch_contact("missing", transport=transport) is None
    assert seen[0] == ("/internal/users/u1/contact", KEY)

    def down(request):
        raise httpx.ConnectError("refused")

    assert await contact_module.fetch_contact("u1", transport=httpx.MockTransport(down)) is None
