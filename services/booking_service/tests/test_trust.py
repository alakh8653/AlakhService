"""Customer trust: start codes, free fixes, shared visits and SOS."""

import re
import time
from datetime import timedelta

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.config import settings
from app.core import trust
from app.core.names import get_name_lookup
from app.core.notifier import get_notifier
from app.core.payments import get_payment_client, get_session_factory
from app.dependencies import (
    get_admin_lookup,
    get_clock,
    get_provider_location_lookup,
    get_shop_name_lookup,
)
from app.main import app
from app.routers.trust import alert_admins
from tests.test_availability import CLOCK, HOURS, MON, ist
from tests.test_availability import book as book_at
from tests.test_payment_sync_and_worker import PAY
from tests.test_shop_bookings_api import SCHEDULES, SESSIONS, auth, close_service, open_service

KEY = "k" * 40
INTERNAL = {"X-Internal-Key": KEY}
OWNER, PROVIDER, ADMIN = auth("owner-1"), auth("staff-1"), auth("ops-1", "admin")
CUSTOMER = "tc1"
TOLD: list = []
ADMINS = ["adm-1", "adm-2"]
LOCATIONS: dict = {}


class Recorder:
    async def send(self, event, recipients, data):
        TOLD.append((event, [(r["user_id"], r["role"]) for r in recipients], data))


@pytest_asyncio.fixture
async def client(monkeypatch):
    engine = await open_service()
    SCHEDULES["shop-1"] = {**HOURS, "guarantee_days": 7}
    CLOCK["now"] = ist(MON, "08:00") - timedelta(days=1)  # Sunday 8 AM in India
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", KEY)
    TOLD.clear()
    LOCATIONS.clear()
    PAY.sent.clear()
    PAY.down = False

    async def names(ids):
        return {i: {"staff-1": "Imran K."}.get(i, "Customer") for i in ids}

    async def shop_name(shop_id):
        return {"shop-1": "Glow Salon"}.get(shop_id)

    async def location(provider_id):
        return LOCATIONS.get(provider_id)

    async def admins():
        return list(ADMINS)

    overrides = {
        get_clock: lambda: lambda: CLOCK["now"],
        get_notifier: Recorder,
        get_name_lookup: lambda: names,
        get_shop_name_lookup: lambda: shop_name,
        get_provider_location_lookup: lambda: location,
        get_admin_lookup: lambda: admins,
        get_payment_client: lambda: PAY,
        get_session_factory: lambda: SESSIONS["factory"],
    }
    app.dependency_overrides.update(overrides)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    await close_service(engine)


def told(event):
    return [(who, data) for e, who, data in TOLD if e == event]


async def status(client, booking_id, to, headers, code=None):
    body = {"status": to} if code is None else {"status": to, "start_code": code}
    return await client.put(f"/api/v1/bookings/{booking_id}/status", json=body, headers=headers)


async def home_visit(client, customer=CUSTOMER, hhmm="10:00", mode="AT_HOME", service="svc-home"):
    """A home visit (or pickup) confirmed and assigned to staff-1; returns the customer's view of it."""
    made = await book_at(client, MON, hhmm, service=service, customer=customer, service_mode=mode, address_id="addr-1")
    assert made.status_code == 201, made.text
    booking = made.json()
    assert (await status(client, booking["id"], "CONFIRMED", OWNER)).status_code == 200
    assigned = await client.post(
        f"/api/v1/bookings/{booking['id']}/assign", json={"provider_id": "staff-1"}, headers=OWNER
    )
    assert assigned.status_code == 200, assigned.text
    return booking


async def started(client, customer=CUSTOMER, hhmm="10:00"):
    booking = await home_visit(client, customer, hhmm)
    assert (await status(client, booking["id"], "PROVIDER_EN_ROUTE", PROVIDER)).status_code == 200
    assert (await status(client, booking["id"], "IN_PROGRESS", PROVIDER, booking["start_code"])).status_code == 200
    return booking


# ------------------------------------------------------------------------------------------ start code


@pytest.mark.asyncio
async def test_only_the_customer_and_admins_see_the_start_code(client):
    booking = await home_visit(client)
    code = booking["start_code"]
    assert re.fullmatch(r"\d{4}", code)
    url = f"/api/v1/bookings/{booking['id']}"
    assert (await client.get(url, headers=auth(CUSTOMER))).json()["start_code"] == code
    assert (await client.get(url, headers=ADMIN)).json()["start_code"] == code
    for party in (OWNER, PROVIDER):
        assert (await client.get(url, headers=party)).json()["start_code"] is None
        listed = (await client.get("/api/v1/bookings/shop/shop-1", headers=OWNER)).json()["items"]
        assert all(b["start_code"] is None for b in listed)
    assigned = (await client.get("/api/v1/bookings/assigned", headers=PROVIDER)).json()["items"]
    assert assigned and all(b["start_code"] is None for b in assigned)
    # Changing the booking returns it without the code to the shop too.
    moved = await status(client, booking["id"], "PROVIDER_EN_ROUTE", PROVIDER)
    assert moved.status_code == 200 and moved.json()["start_code"] is None
    # A visit at the shop has none.
    at_shop = (await book_at(client, MON, "11:00", service="svc-home", customer=CUSTOMER)).json()
    assert at_shop["start_code"] is None


@pytest.mark.asyncio
async def test_a_home_visit_starts_only_with_the_customers_code(client):
    booking = await home_visit(client)
    bid, code = booking["id"], booking["start_code"]
    assert (await status(client, bid, "PROVIDER_EN_ROUTE", PROVIDER)).status_code == 200
    missing = await status(client, bid, "IN_PROGRESS", PROVIDER)
    assert missing.status_code == 422 and missing.json()["detail"] == trust.START_CODE_MESSAGE
    wrong = str((int(code) + 1) % 10000).zfill(4)
    # The shop owner too needs the code (the dashboard sends it in the same body).
    assert (await status(client, bid, "IN_PROGRESS", OWNER)).status_code == 422
    assert (await status(client, bid, "IN_PROGRESS", OWNER, wrong)).status_code == 422
    ok = await status(client, bid, "IN_PROGRESS", OWNER, code)
    assert ok.status_code == 200 and ok.json()["status"] == "IN_PROGRESS"


@pytest.mark.asyncio
async def test_five_wrong_codes_in_15_minutes_lock_the_start(client):
    booking = await home_visit(client)
    bid, code = booking["id"], booking["start_code"]
    wrong = str((int(code) + 1) % 10000).zfill(4)
    await status(client, bid, "PROVIDER_EN_ROUTE", PROVIDER)
    for _ in range(trust.MAX_START_CODE_TRIES):
        assert (await status(client, bid, "IN_PROGRESS", PROVIDER, wrong)).status_code == 422
    locked = await status(client, bid, "IN_PROGRESS", PROVIDER, code)  # even the right code now
    assert locked.status_code == 429 and "Retry-After" in locked.headers
    CLOCK["now"] += timedelta(minutes=16)
    assert (await status(client, bid, "IN_PROGRESS", PROVIDER, code)).status_code == 200


@pytest.mark.asyncio
async def test_wrong_tries_spread_over_time_do_not_lock_and_admins_skip_the_code(client):
    booking = await home_visit(client)
    bid, code = booking["id"], booking["start_code"]
    wrong = str((int(code) + 1) % 10000).zfill(4)
    await status(client, bid, "PROVIDER_EN_ROUTE", PROVIDER)
    for _ in range(4):
        assert (await status(client, bid, "IN_PROGRESS", PROVIDER, wrong)).status_code == 422
    CLOCK["now"] += timedelta(minutes=16)  # a new window
    for _ in range(4):
        assert (await status(client, bid, "IN_PROGRESS", PROVIDER, wrong)).status_code == 422
    assert (await status(client, bid, "IN_PROGRESS", ADMIN)).status_code == 200


@pytest.mark.asyncio
async def test_a_pickup_is_collected_only_with_the_code(client):
    booking = await home_visit(client, mode="PICKUP_DROP", service="svc-repair")
    bid, code = booking["id"], booking["start_code"]
    assert code
    assert (await status(client, bid, "PICKED_UP", PROVIDER)).status_code == 422
    assert (await status(client, bid, "PICKED_UP", PROVIDER, code)).status_code == 200
    # Work at the shop on the collected item needs no code.
    assert (await status(client, bid, "IN_PROGRESS", OWNER)).status_code == 200


@pytest.mark.asyncio
async def test_an_invalid_move_does_not_cost_a_try(client):
    booking = await home_visit(client)
    for _ in range(trust.MAX_START_CODE_TRIES + 1):
        # Not on the way yet for a pickup step: refused as a bad move, never counted as a guess.
        assert (await status(client, booking["id"], "PICKED_UP", PROVIDER, "0000")).status_code == 400
    await status(client, booking["id"], "PROVIDER_EN_ROUTE", PROVIDER)
    ok = await status(client, booking["id"], "IN_PROGRESS", PROVIDER, booking["start_code"])
    assert ok.status_code == 200


# ------------------------------------------------------------------------------------------ free fix


async def completed(client, customer=CUSTOMER):
    booking = await started(client, customer)
    assert (await status(client, booking["id"], "COMPLETED", PROVIDER)).status_code == 200
    return booking


@pytest.mark.asyncio
async def test_the_customer_gets_one_free_fix_within_the_guarantee(client):
    booking = await completed(client)
    bid = booking["id"]
    seen = (await client.get(f"/api/v1/bookings/{bid}", headers=auth(CUSTOMER))).json()
    until = seen["guarantee_until"]
    assert until is not None
    url = f"/api/v1/bookings/{bid}/rework"
    reason = {"reason": "The colour washed out in two days"}
    assert (await client.post(url, json=reason, headers=OWNER)).status_code == 403
    assert (await client.post(url, json=reason, headers=auth("stranger"))).status_code == 404
    assert (await client.post(url, json={"reason": "bad"}, headers=auth(CUSTOMER))).status_code == 422

    TOLD.clear()
    made = await client.post(url, json=reason, headers=auth(CUSTOMER))
    assert made.status_code == 201, made.text
    fix = made.json()
    assert (fix["status"], fix["total_amount"], fix["rework_of"]) == ("PENDING", 0, bid)
    assert (fix["shop_id"], fix["service_id"], fix["service_mode"]) == ("shop-1", "svc-home", "AT_HOME")
    assert re.fullmatch(r"\d{4}", fix["start_code"])  # a home visit again: it starts with a code too
    [(who, data)] = told("booking.created")
    assert who == [("owner-1", "shop")] and data["rework"] is True
    original = (await client.get(f"/api/v1/bookings/{bid}", headers=auth(CUSTOMER))).json()
    assert original["rework_booking_id"] == fix["id"]
    again = await client.post(url, json=reason, headers=auth(CUSTOMER))
    assert again.status_code == 409
    # A free fix is not itself fixed for free again.
    assert (
        await client.post(f"/api/v1/bookings/{fix['id']}/rework", json=reason, headers=auth(CUSTOMER))
    ).status_code == 409


@pytest.mark.asyncio
async def test_no_free_fix_before_completion_or_after_the_guarantee(client):
    booking = await started(client)
    url = f"/api/v1/bookings/{booking['id']}/rework"
    reason = {"reason": "The colour washed out in two days"}
    assert (await client.post(url, json=reason, headers=auth(CUSTOMER))).status_code == 409
    assert (await status(client, booking["id"], "COMPLETED", PROVIDER)).status_code == 200
    CLOCK["now"] += timedelta(days=7, minutes=1)
    late = await client.post(url, json=reason, headers=auth(CUSTOMER))
    assert late.status_code == 409 and late.json()["detail"] == trust.GUARANTEE_ENDED_MESSAGE


@pytest.mark.asyncio
async def test_the_guarantee_follows_the_shops_days(client):
    SCHEDULES["shop-1"] = {**HOURS, "guarantee_days": 0}
    booking = await completed(client)
    CLOCK["now"] += timedelta(minutes=1)
    late = await client.post(
        f"/api/v1/bookings/{booking['id']}/rework", json={"reason": "Not fixed properly"}, headers=auth(CUSTOMER)
    )
    assert late.status_code == 409


# ------------------------------------------------------------------------------------------ shared visit


@pytest.mark.asyncio
async def test_the_customer_shares_a_visit_without_anyones_contact_details(client):
    booking = await home_visit(client)
    url = f"/api/v1/bookings/{booking['id']}/share"
    assert (await client.post(url, headers=OWNER)).status_code == 403
    assert (await client.post(url, headers=PROVIDER)).status_code == 403
    assert (await client.post(url, headers=auth("stranger"))).status_code == 404
    shared = await client.post(url, headers=auth(CUSTOMER))
    assert shared.status_code == 200
    link = shared.json()["url"]
    assert link.startswith("https://alakhservice.in/v/")
    assert (await client.post(url, headers=auth(CUSTOMER))).json()["url"] == link  # the same link each time
    token = link.rsplit("/", 1)[1]

    public = await client.get(f"/api/v1/public/shares/{token}")  # no login
    assert public.status_code == 200
    body = public.json()
    assert body == {
        "shop_name": "Glow Salon",
        "service_name": "Haircut at home",
        "status": "ASSIGNED",
        "scheduled_at": body["scheduled_at"],
        "provider_first_name": "Imran",
        "provider_location": None,
        "eta": body["scheduled_at"],  # not on the way yet: the booked time
    }
    for secret in (CUSTOMER, "addr-1", "staff-1", "Imran K.", booking["start_code"]):
        assert secret not in public.text

    # The professional's position shows only while they are on the way.
    LOCATIONS["staff-1"] = {"lat": 12.97, "lng": 77.59, "updated_at": None}
    await status(client, booking["id"], "PROVIDER_EN_ROUTE", PROVIDER)
    on_way = (await client.get(f"/api/v1/public/shares/{token}")).json()
    assert on_way["provider_location"] == {"lat": 12.97, "lng": 77.59, "updated_at": None}
    assert on_way["eta"] is not None
    await status(client, booking["id"], "IN_PROGRESS", PROVIDER, booking["start_code"])
    started_view = (await client.get(f"/api/v1/public/shares/{token}")).json()
    assert (started_view["provider_location"], started_view["eta"]) == (None, None)

    assert (await client.get("/api/v1/public/shares/not-a-token")).status_code == 404
    CLOCK["now"] = ist(MON, "10:00") + timedelta(hours=24)  # a day after the visit
    assert (await client.get(f"/api/v1/public/shares/{token}")).status_code == 404
    assert (await client.post(url, headers=auth(CUSTOMER))).status_code == 409


@pytest.mark.asyncio
async def test_the_share_link_uses_the_configured_site(client, monkeypatch):
    monkeypatch.setattr(settings, "SHARE_BASE_URL", "https://alakh-ci.in/")
    booking = (await book_at(client, MON, "12:00", service="svc-a", customer=CUSTOMER)).json()
    shared = (await client.post(f"/api/v1/bookings/{booking['id']}/share", headers=auth(CUSTOMER))).json()
    assert re.fullmatch(r"https://alakh-ci\.in/v/[\w-]{20,64}", shared["url"])
    assert shared["expires_at"].startswith("2030-11-05T06:30")  # 24 hours after 12:00 IST


# ------------------------------------------------------------------------------------------ SOS


@pytest.mark.asyncio
async def test_sos_alerts_every_admin_and_offers_112(client):
    booking = await home_visit(client)
    url = f"/api/v1/bookings/{booking['id']}/sos"
    assert (await client.post(url, json={}, headers=OWNER)).status_code == 403
    assert (await client.post(url, json={}, headers=auth("stranger"))).status_code == 404
    raised = await client.post(url, json={"lat": 12.9, "lng": 77.6, "note": "Call 9876543210"}, headers=auth(CUSTOMER))
    assert raised.status_code == 201
    assert raised.json()["emergency_number"] == "112" and raised.json()["alert_id"]
    [(who, data)] = told("safety.sos")
    assert who == [("adm-1", "admin"), ("adm-2", "admin")]
    assert (data["booking_number"], data["role"], data["location"]) == (
        booking["booking_number"],
        "customer",
        "12.90000, 77.60000",
    )
    assert "9876543210" not in data["note"]
    assert (await client.post(url, json={"lat": 91}, headers=PROVIDER)).status_code == 422
    CLOCK["now"] += timedelta(minutes=1)
    assert (await client.post(url, json={}, headers=PROVIDER)).status_code == 201

    listed = await client.get("/api/v1/admin/safety/sos", headers=ADMIN)
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert [a["role"] for a in items] == ["provider", "customer"] and listed.json()["total"] == 2
    assert items[1]["booking_number"] == booking["booking_number"]
    assert (await client.get("/api/v1/admin/safety/sos", headers=auth(CUSTOMER))).status_code == 403
    assert (await client.get("/api/v1/admin/safety/sos", headers=OWNER)).status_code == 403


@pytest.mark.asyncio
async def test_no_more_than_three_sos_per_booking_in_ten_minutes(client):
    booking = await home_visit(client)
    url = f"/api/v1/bookings/{booking['id']}/sos"
    for _ in range(trust.MAX_SOS_ALERTS):
        assert (await client.post(url, json={}, headers=auth(CUSTOMER))).status_code == 201
    limited = await client.post(url, json={}, headers=PROVIDER)
    assert limited.status_code == 429 and "112" in limited.json()["detail"]
    assert len(told("safety.sos")) == trust.MAX_SOS_ALERTS
    CLOCK["now"] += timedelta(minutes=10, seconds=1)
    assert (await client.post(url, json={}, headers=auth(CUSTOMER))).status_code == 201


@pytest.mark.asyncio
async def test_sos_with_admins_unreachable_is_still_recorded(client):
    ADMINS.clear()
    try:
        booking = await home_visit(client)
        resp = await client.post(f"/api/v1/bookings/{booking['id']}/sos", json={}, headers=auth(CUSTOMER))
        assert resp.status_code == 201 and told("safety.sos") == []
        assert (await client.get("/api/v1/admin/safety/sos", headers=ADMIN)).json()["total"] == 1
    finally:
        ADMINS.extend(["adm-1", "adm-2"])


@pytest.mark.asyncio
async def test_more_admins_than_one_event_takes_are_told_in_batches(client):
    sent = []

    class Batches:
        async def send(self, event, recipients, data):
            sent.append(len(recipients))

    async def many():
        return [f"adm-{i}" for i in range(45)]

    await alert_admins(Batches(), many, {"booking_id": "b"})
    assert sent == [20, 20, 5]


# ------------------------------------------------------------------------------------------ peers


REAL_CLIENT = httpx.AsyncClient


def _mock(monkeypatch, handler):
    from app import dependencies

    monkeypatch.setattr(
        dependencies.httpx, "AsyncClient", lambda **kw: REAL_CLIENT(transport=httpx.MockTransport(handler), **kw)
    )


@pytest.mark.asyncio
async def test_admins_are_found_through_auth_services_internal_route(monkeypatch):
    from app import dependencies

    calls = []

    def handler(request):
        calls.append((request.url.path, request.headers.get("X-Internal-Key")))
        return httpx.Response(200, json={"user_ids": ["a1", "a2", 3]})

    _mock(monkeypatch, handler)
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", KEY)
    assert await dependencies.fetch_admin_ids() == ["a1", "a2"]
    assert calls == [("/internal/users/admins", KEY)]
    _mock(monkeypatch, lambda request: httpx.Response(503))
    assert await dependencies.fetch_admin_ids() == []
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", "")
    assert await dependencies.fetch_admin_ids() == []


@pytest.mark.asyncio
async def test_the_providers_position_is_asked_with_a_one_minute_token_in_their_name(monkeypatch):
    from app import dependencies

    seen = {}

    def handler(request):
        token = request.headers["Authorization"].split()[1]
        seen.update(path=request.url.raw_path.decode(), claims=jwt.get_unverified_claims(token))
        return httpx.Response(200, json={"latitude": 12.9, "longitude": 77.6, "timestamp": "2030-11-04T04:30:00Z"})

    _mock(monkeypatch, handler)
    before = time.time()
    assert await dependencies.fetch_provider_location("staff/1") == {
        "lat": 12.9,
        "lng": 77.6,
        "updated_at": "2030-11-04T04:30:00Z",
    }
    assert seen["path"] == "/api/v1/locations/staff%2F1"
    assert (seen["claims"]["sub"], seen["claims"]["type"]) == ("staff/1", "access")
    assert seen["claims"]["exp"] <= before + 61
    _mock(monkeypatch, lambda request: httpx.Response(404))
    assert await dependencies.fetch_provider_location("staff-1") is None


@pytest.mark.asyncio
async def test_the_shop_name_comes_from_shop_service(monkeypatch):
    from app import dependencies

    dependencies._shop_name_cache.clear()
    _mock(monkeypatch, lambda request: httpx.Response(200, json={"name": "Glow Salon", "phone": "9876543210"}))
    assert await dependencies.fetch_shop_name("shop-x") == "Glow Salon"
    _mock(monkeypatch, lambda request: httpx.Response(404))
    assert await dependencies.fetch_shop_name("shop-y") is None
