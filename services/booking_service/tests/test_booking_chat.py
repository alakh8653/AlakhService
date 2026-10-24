"""Booking chat and masked calls: only the booking's people, only while it is open, contact details hidden."""

import base64
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs

import httpx
import pytest

from app.config import settings
from app.core import risk, telephony
from app.core.names import get_name_lookup
from app.core.notifier import get_notifier
from app.core.telephony import CallFailed, DisabledBridge, ExotelBridge, PlacedCall, get_call_bridge, get_number_lookup
from app.dependencies import get_clock
from app.main import app
from app.routers import chat
from tests.test_shop_bookings_api import SESSIONS, auth, booking, client  # noqa: F401  (the fixture)

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
MASK = "[hidden for your safety]"
NUMBERS = {"c3": "+919800000003", "staff-1": "+919800000001", "owner-1": "+919800000009", "c1": "+919800000011"}
# bk-4: PENDING at shop-1 (owner-1), customer c3, provider staff-1.
URL = "/api/v1/bookings/bk-4/messages"
CUSTOMER, OWNER, PROVIDER = auth("c3"), auth("owner-1"), auth("staff-1")


class Clock:
    def __init__(self):
        self.now = NOW

    def __call__(self):
        return self.now


class Notified:
    def __init__(self):
        self.sent = []

    async def send(self, event, recipients, data):
        self.sent.append((event, [(r["user_id"], r["role"]) for r in recipients], data))


class FakeBridge:
    name = "fake"
    enabled = True

    def __init__(self):
        self.calls = []
        self.fail = False

    async def connect(self, caller_number, callee_number, reference):
        if self.fail:
            raise CallFailed("down")
        self.calls.append((caller_number, callee_number, reference))
        return PlacedCall(call_id="prov-123", status="queued")


@pytest.fixture
def env(client, monkeypatch):  # noqa: F811
    clock, notified, bridge, risks = Clock(), Notified(), FakeBridge(), []

    async def names(user_ids):
        return {uid: {"c3": "Asha R.", "c1": "Ravi S."}.get(uid, "Customer") for uid in user_ids}

    async def number(user_id):
        return NUMBERS.get(user_id)

    async def fake_risk(user_id, signal_type, value, is_risk_event):
        risks.append((user_id, signal_type))

    monkeypatch.setattr(risk, "report_risk", fake_risk)
    app.dependency_overrides[get_clock] = lambda: clock
    app.dependency_overrides[get_notifier] = lambda: notified
    app.dependency_overrides[get_name_lookup] = lambda: names
    app.dependency_overrides[get_number_lookup] = lambda: number
    app.dependency_overrides[get_call_bridge] = lambda: DisabledBridge()
    return {"clock": clock, "notified": notified, "bridge": bridge, "risks": risks}


def enable_calls(env):
    app.dependency_overrides[get_call_bridge] = lambda: env["bridge"]


async def closed_booking(n, status, closed_ago: timedelta):
    b = booking(n, "shop-1", status, 1, customer="c3", provider="staff-1")
    b.updated_at = NOW - closed_ago
    async with SESSIONS["factory"]() as db:
        db.add(b)
        await db.commit()
    return f"/api/v1/bookings/bk-{n}"


@pytest.mark.asyncio
async def test_customer_and_shop_talk_and_see_read_receipts(client, env):  # noqa: F811
    sent = await client.post(URL, json={"body": "  Is 10 am fine?  "}, headers=CUSTOMER)
    assert sent.status_code == 201
    msg = sent.json()
    assert (msg["body"], msg["sender_role"], msg["sender_name"], msg["is_mine"], msg["flagged"]) == (
        "Is 10 am fine?",
        "customer",
        "Asha R.",
        True,
        False,
    )
    env["clock"].now += timedelta(seconds=5)
    assert (await client.post(URL, json={"body": "Yes, see you"}, headers=OWNER)).status_code == 201
    env["clock"].now += timedelta(seconds=5)
    assert (await client.post(URL, json={"body": "On my way"}, headers=PROVIDER)).json()["sender_name"] == "Provider"

    shop_view = (await client.get(URL, headers=OWNER)).json()
    assert [m["body"] for m in shop_view["items"]] == ["Is 10 am fine?", "Yes, see you", "On my way"]
    assert [m["is_mine"] for m in shop_view["items"]] == [False, True, False]
    assert [m["sender_name"] for m in shop_view["items"]] == ["Asha R.", "Shop", "Provider"]
    assert (shop_view["total"], shop_view["unread"], shop_view["can_send"]) == (3, 1, True)
    assert shop_view["open_until"] is None and shop_view["calling_enabled"] is False
    for m in shop_view["items"]:
        assert not {"sender_id", "phone", "email", "original_body"} & set(m)

    customer_view = (await client.get(URL, headers=CUSTOMER)).json()
    assert customer_view["unread"] == 2
    assert (await client.post(URL + "/read", headers=CUSTOMER)).json() == {"marked": 2}
    assert (await client.get(URL, headers=CUSTOMER)).json()["unread"] == 0
    shop_items = (await client.get(URL, headers=OWNER)).json()["items"]
    assert shop_items[0]["read_at"] is None  # the shop has not read the customer's yet
    assert shop_items[1]["read_at"] is not None


@pytest.mark.asyncio
async def test_pages_newest_first_each_oldest_first(client, env):  # noqa: F811
    for i in range(5):
        env["clock"].now += timedelta(seconds=10)
        await client.post(URL, json={"body": f"m{i}"}, headers=CUSTOMER)
    first = (await client.get(URL, params={"per_page": 2}, headers=OWNER)).json()
    second = (await client.get(URL, params={"per_page": 2, "page": 2}, headers=OWNER)).json()
    assert [m["body"] for m in first["items"]] == ["m3", "m4"]
    assert [m["body"] for m in second["items"]] == ["m1", "m2"]
    assert first["total"] == 5


@pytest.mark.asyncio
async def test_only_the_bookings_people_take_part(client, env):  # noqa: F811
    await client.post(URL, json={"body": "hello"}, headers=CUSTOMER)
    for outsider in (auth("c1"), auth("owner-2"), auth("staff-2")):
        assert (await client.get(URL, headers=outsider)).status_code == 404
        assert (await client.post(URL, json={"body": "hi"}, headers=outsider)).status_code == 404
    assert (await client.get(URL)).status_code in (401, 403)
    admin = auth("ops", "admin")
    view = (await client.get(URL, headers=admin)).json()
    assert (view["total"], view["can_send"]) == (1, False)
    assert (await client.post(URL, json={"body": "hi"}, headers=admin)).status_code == 403
    assert (await client.post(URL + "/read", headers=admin)).json() == {"marked": 0}
    assert (await client.get("/api/v1/bookings/nope/messages", headers=CUSTOMER)).status_code == 404


@pytest.mark.asyncio
async def test_contact_details_are_hidden_flagged_and_reported(client, env):  # noqa: F811
    msg = (await client.post(URL, json={"body": "call me 98765 43210 or ravi@gmail.com"}, headers=CUSTOMER)).json()
    assert msg["body"] == f"call me {MASK} or {MASK}"
    assert msg["flagged"] is True
    assert "98765" not in str((await client.get(URL, headers=OWNER)).json())
    assert env["risks"] == [("c3", "contact_sharing_attempt")]

    env["clock"].now += timedelta(seconds=5)
    await client.post(URL, json={"body": "whatsapp me"}, headers=OWNER)
    env["clock"].now += timedelta(seconds=5)
    await client.post(URL, json={"body": "my upi is asha@okaxis"}, headers=CUSTOMER)
    await client.post(URL, json={"body": "thanks"}, headers=CUSTOMER)

    admin = auth("ops", "admin")
    flagged = (await client.get("/api/v1/chat-moderation/flagged", headers=admin)).json()
    assert flagged["total"] == 3
    newest = flagged["items"][0]
    assert (newest["sender_id"], newest["original_body"], newest["flag_reasons"]) == (
        "c3",
        "my upi is asha@okaxis",
        ["upi"],
    )
    assert flagged["items"][2]["flag_reasons"] == ["email", "phone"]
    only_owner = await client.get("/api/v1/chat-moderation/flagged", params={"sender_id": "owner-1"}, headers=admin)
    assert only_owner.json()["total"] == 1

    offenders = (await client.get("/api/v1/chat-moderation/repeat-offenders", headers=admin)).json()
    assert offenders["min_attempts"] == 2
    assert [(o["user_id"], o["attempts"], o["bookings"], o["sender_role"]) for o in offenders["items"]] == [
        ("c3", 2, 1, "customer")
    ]
    everyone = (
        await client.get("/api/v1/chat-moderation/repeat-offenders", params={"min_attempts": 1}, headers=admin)
    ).json()
    assert {o["user_id"] for o in everyone["items"]} == {"c3", "owner-1"}

    for path in ("/api/v1/chat-moderation/flagged", "/api/v1/chat-moderation/repeat-offenders"):
        assert (await client.get(path, headers=OWNER)).status_code == 403


@pytest.mark.asyncio
async def test_the_chat_closes_a_day_after_the_booking_does(client, env):  # noqa: F811
    recent = await closed_booking(40, "COMPLETED", timedelta(hours=23))
    old = await closed_booking(41, "CANCELLED", timedelta(hours=25))
    assert (
        await client.post(recent + "/messages", json={"body": "left my umbrella"}, headers=CUSTOMER)
    ).status_code == 201
    view = (await client.get(recent + "/messages", headers=OWNER)).json()
    assert view["can_send"] is True
    assert view["open_until"].startswith((NOW + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"))

    refused = await client.post(old + "/messages", json={"body": "hello?"}, headers=CUSTOMER)
    assert (refused.status_code, refused.json()["detail"]) == (409, "This booking is closed; its chat is read-only")
    closed = (await client.get(old + "/messages", headers=CUSTOMER)).json()
    assert (closed["can_send"], closed["calling_enabled"]) == (False, False)


@pytest.mark.asyncio
async def test_messages_are_rate_limited_and_bounded(client, env):  # noqa: F811
    for i in range(chat.MAX_MESSAGES_PER_MINUTE):
        assert (await client.post(URL, json={"body": f"m{i}"}, headers=CUSTOMER)).status_code == 201
    assert (await client.post(URL, json={"body": "one more"}, headers=CUSTOMER)).status_code == 429
    # The shop is limited separately.
    assert (await client.post(URL, json={"body": "ok"}, headers=OWNER)).status_code == 201
    env["clock"].now += timedelta(seconds=61)
    assert (await client.post(URL, json={"body": "one more"}, headers=CUSTOMER)).status_code == 201

    assert (await client.post(URL, json={"body": "x" * 1001}, headers=CUSTOMER)).status_code == 422
    assert (await client.post(URL, json={"body": "   "}, headers=CUSTOMER)).status_code == 422
    assert (await client.post(URL, json={"body": "x" * 1000}, headers=OWNER)).status_code == 201


@pytest.mark.asyncio
async def test_the_other_side_is_told_of_the_first_unread_message_only(client, env):  # noqa: F811
    sent = env["notified"].sent
    await client.post(URL, json={"body": "hello"}, headers=CUSTOMER)
    assert sent == [
        (
            "booking.message",
            [("owner-1", "shop"), ("staff-1", "provider")],
            {"booking_id": "bk-4", "booking_number": "BK-4"},
        )
    ]
    await client.post(URL, json={"body": "are you there?"}, headers=CUSTOMER)
    assert len(sent) == 1
    await client.post(URL, json={"body": "yes"}, headers=PROVIDER)
    assert sent[-1][:2] == ("booking.message", [("c3", "customer")])
    await client.post(URL + "/read", headers=OWNER)
    await client.post(URL, json={"body": "great"}, headers=CUSTOMER)
    assert len(sent) == 3
    assert "great" not in str(sent)


@pytest.mark.asyncio
async def test_calling_is_off_by_default(client, env):  # noqa: F811
    resp = await client.post("/api/v1/bookings/bk-4/call", headers=CUSTOMER)
    assert (resp.status_code, resp.json()["detail"]) == (501, "Calling is not enabled. Please use the chat.")
    assert (await client.get(URL, headers=CUSTOMER)).json()["calling_enabled"] is False


@pytest.mark.asyncio
async def test_masked_calls_ring_both_sides_without_revealing_numbers(client, env):  # noqa: F811
    enable_calls(env)
    calls = env["bridge"].calls
    assert (await client.get(URL, headers=CUSTOMER)).json()["calling_enabled"] is True

    # PENDING: nobody is on the job yet, so the customer reaches the shop owner.
    resp = await client.post("/api/v1/bookings/bk-4/call", headers=CUSTOMER)
    assert resp.status_code == 202
    body = resp.json()
    assert (body["status"], body["callee"]) == ("queued", "shop")
    assert calls[-1] == (NUMBERS["c3"], NUMBERS["owner-1"], "BK-4")
    assert "+91" not in resp.text and "prov-123" not in resp.text

    resp = await client.post("/api/v1/bookings/bk-4/call", headers=PROVIDER)
    assert resp.json()["callee"] == "customer"
    assert calls[-1] == (NUMBERS["staff-1"], NUMBERS["c3"], "BK-4")

    # Once the provider is on the job the customer reaches them.
    async with SESSIONS["factory"]() as db:
        from app.models.booking import Booking

        (await db.get(Booking, "bk-4")).status = "ASSIGNED"
        await db.commit()
    assert (await client.post("/api/v1/bookings/bk-4/call", headers=CUSTOMER)).json()["callee"] == "provider"


@pytest.mark.asyncio
async def test_calls_follow_the_chat_rules(client, env):  # noqa: F811
    enable_calls(env)
    assert (await client.post("/api/v1/bookings/bk-4/call", headers=auth("c1"))).status_code == 404
    assert (await client.post("/api/v1/bookings/bk-4/call", headers=auth("ops", "admin"))).status_code == 403
    old = await closed_booking(50, "COMPLETED", timedelta(days=3))
    assert (await client.post(old + "/call", headers=CUSTOMER)).status_code == 409

    for _ in range(chat.MAX_CALLS_PER_10_MINUTES):
        assert (await client.post("/api/v1/bookings/bk-4/call", headers=CUSTOMER)).status_code == 202
    assert (await client.post("/api/v1/bookings/bk-4/call", headers=CUSTOMER)).status_code == 429
    env["clock"].now += timedelta(minutes=11)

    env["bridge"].fail = True
    assert (await client.post("/api/v1/bookings/bk-4/call", headers=CUSTOMER)).status_code == 502
    env["bridge"].fail = False

    NUMBERS_BACKUP = dict(NUMBERS)
    try:
        del NUMBERS["c3"]
        resp = await client.post("/api/v1/bookings/bk-4/call", headers=CUSTOMER)
        assert (resp.status_code, resp.json()["detail"]) == (409, "Add a phone number to your account to make calls")
        resp = await client.post("/api/v1/bookings/bk-4/call", headers=OWNER)
        assert resp.status_code == 409 and "send a message" in resp.json()["detail"]
    finally:
        NUMBERS.update(NUMBERS_BACKUP)


@pytest.mark.asyncio
async def test_exotel_bridge_posts_a_click_to_call():
    seen = []

    def handler(request: httpx.Request):
        seen.append(request)
        return httpx.Response(200, json={"Call": {"Sid": "abc123", "Status": "in-progress"}})

    bridge = ExotelBridge("key", "token", "acct", "08047xxxxxx", "api.in.exotel.com", httpx.MockTransport(handler))
    placed = await bridge.connect("+919800000001", "+919800000002", "BK-1")
    assert (placed.call_id, placed.status) == ("abc123", "in-progress")
    request = seen[0]
    assert str(request.url) == "https://api.in.exotel.com/v1/Accounts/acct/Calls/connect.json"
    assert request.headers["Authorization"] == "Basic " + base64.b64encode(b"key:token").decode()
    form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
    assert form == {"From": "+919800000001", "To": "+919800000002", "CallerId": "08047xxxxxx", "CustomField": "BK-1"}

    refused = ExotelBridge("k", "t", "a", "c", transport=httpx.MockTransport(lambda r: httpx.Response(403)))
    with pytest.raises(CallFailed):
        await refused.connect("1", "2", "BK")

    def down(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(CallFailed):
        await ExotelBridge("k", "t", "a", "c", transport=httpx.MockTransport(down)).connect("1", "2", "BK")


def test_the_bridge_comes_from_settings(monkeypatch):
    assert telephony.bridge_from_settings().enabled is False  # CALL_PROVIDER=none by default
    monkeypatch.setattr(settings, "CALL_PROVIDER", "exotel")
    assert telephony.bridge_from_settings().enabled is False  # no credentials: stays off
    for name, value in (
        ("EXOTEL_API_KEY", "k"),
        ("EXOTEL_API_TOKEN", "t"),
        ("EXOTEL_ACCOUNT_SID", "a"),
        ("EXOTEL_CALLER_ID", "080"),
    ):
        monkeypatch.setattr(settings, name, value)
    bridge = telephony.bridge_from_settings()
    assert isinstance(bridge, ExotelBridge) and bridge.enabled
    monkeypatch.setattr(settings, "CALL_PROVIDER", "twilio")
    assert telephony.bridge_from_settings().enabled is False


@pytest.mark.asyncio
async def test_numbers_come_from_auth_service_internally(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", "")
    assert await telephony.fetch_call_number("u1") is None  # not configured: nobody can be called
