"""A shop sees its customers by display name only, never their contact details."""

import httpx
import pytest

from app.config import settings
from app.core import names
from app.core.names import get_name_lookup
from app.main import app
from app.models.booking import Booking, BookingStatusHistory
from tests.test_shop_bookings_api import SESSIONS, auth, booking, client  # noqa: F401  (the fixture)

NAMES = {"c1": "Ravi S.", "c3": "Asha R."}
# Nothing a shop-facing response may carry about the customer.
CONTACT_FIELDS = {"customer_phone", "customer_email", "customer_name", "phone", "email", "full_name"}


@pytest.fixture
def named(client):  # noqa: F811
    asked = []

    async def fake_names(user_ids):
        ids = list(user_ids)
        asked.append(ids)
        return {uid: NAMES.get(uid, "Customer") for uid in ids}

    app.dependency_overrides[get_name_lookup] = lambda: fake_names
    return asked


async def _add(*rows):
    async with SESSIONS["factory"]() as db:
        db.add_all(rows)
        await db.commit()


def _home_visit(n, status, notes=None):
    b = booking(n, "shop-1", status, 5, customer="c1", provider="staff-1")
    b.service_mode = "AT_HOME"
    b.address_id = "addr-1"
    b.notes = notes
    return b


@pytest.mark.asyncio
async def test_shop_lists_show_display_names_in_one_lookup(client, named):  # noqa: F811
    page = (await client.get("/api/v1/bookings/shop/shop-1", headers=auth("owner-1"))).json()
    by_id = {b["id"]: b for b in page["items"]}
    assert by_id["bk-1"]["customer_display_name"] == "Ravi S."
    assert by_id["bk-4"]["customer_display_name"] == "Asha R."
    assert by_id["bk-2"]["customer_display_name"] == "Customer"
    assert len(named) == 1 and set(named[0]) == {"c1", "c2", "c3"}
    for item in page["items"]:
        assert not CONTACT_FIELDS & set(item)


@pytest.mark.asyncio
async def test_every_booking_response_carries_the_display_name(client, named):  # noqa: F811
    for who, url in (
        ("owner-1", "/api/v1/bookings/bk-4"),
        ("staff-1", "/api/v1/bookings/bk-4"),
        ("c3", "/api/v1/bookings/bk-4"),
    ):
        body = (await client.get(url, headers=auth(who))).json()
        assert body["customer_display_name"] == "Asha R."
        assert not CONTACT_FIELDS & set(body)
    assigned = (await client.get("/api/v1/bookings/assigned", headers=auth("staff-1"))).json()
    assert {b["customer_display_name"] for b in assigned["items"]} == {"Ravi S.", "Asha R."}
    confirmed = await client.put("/api/v1/bookings/bk-4/status", json={"status": "CONFIRMED"}, headers=auth("owner-1"))
    assert confirmed.json()["customer_display_name"] == "Asha R."


@pytest.mark.asyncio
async def test_the_address_is_shown_to_the_shop_only_for_an_open_home_visit(client, named):  # noqa: F811
    await _add(_home_visit(20, "ASSIGNED"), _home_visit(21, "COMPLETED"))
    open_job = booking(22, "shop-1", "CONFIRMED", 5, customer="c1")
    open_job.address_id = "addr-1"  # at the shop: the address is not needed
    await _add(open_job)
    for who in ("owner-1", "staff-1"):
        assert (await client.get("/api/v1/bookings/bk-20", headers=auth(who))).json()["address_id"] == "addr-1"
        assert (await client.get("/api/v1/bookings/bk-21", headers=auth(who))).json()["address_id"] is None
    assert (await client.get("/api/v1/bookings/bk-22", headers=auth("owner-1"))).json()["address_id"] is None
    # The customer and admins always see their own.
    assert (await client.get("/api/v1/bookings/bk-21", headers=auth("c1"))).json()["address_id"] == "addr-1"
    assert (await client.get("/api/v1/bookings/bk-21", headers=auth("ops", "admin"))).json()["address_id"] == "addr-1"


@pytest.mark.asyncio
async def test_contact_details_in_notes_and_reasons_are_hidden_from_the_other_side(client, named):  # noqa: F811
    await _add(_home_visit(30, "ASSIGNED", notes="Gate code 4321, call 98765 43210"))
    await _add(
        BookingStatusHistory(
            id="h-30", booking_id="bk-30", to_status="ASSIGNED", changed_by="owner-1", reason="ring +91 91234 56789"
        )
    )
    shop_view = (await client.get("/api/v1/bookings/bk-30", headers=auth("owner-1"))).json()
    assert shop_view["notes"] == "Gate code 4321, call [hidden for your safety]"
    assert (await client.get("/api/v1/bookings/bk-30", headers=auth("c1"))).json()["notes"].endswith("98765 43210")
    history = (await client.get("/api/v1/bookings/bk-30/history", headers=auth("c1"))).json()
    assert history[0]["reason"] == "ring [hidden for your safety]"


@pytest.mark.asyncio
async def test_names_unavailable_reads_customer(client):  # noqa: F811
    async def broken(user_ids):
        raise RuntimeError("auth_service down")

    app.dependency_overrides[get_name_lookup] = lambda: broken
    page = await client.get("/api/v1/bookings/shop/shop-1", headers=auth("owner-1"))
    assert page.status_code == 200
    assert {b["customer_display_name"] for b in page.json()["items"]} == {"Customer"}


@pytest.mark.asyncio
async def test_the_lookup_asks_auth_service_once_and_caches(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", "k" * 40)
    monkeypatch.setattr(names, "_cache", {})
    calls = []

    def handler(request: httpx.Request):
        calls.append(request)
        assert request.url.path == "/internal/users/display-names"
        assert request.headers["X-Internal-Key"] == "k" * 40
        return httpx.Response(200, json={"names": {"c1": "Ravi S."}})

    transport = httpx.MockTransport(handler)
    assert await names.fetch_display_names(["c1", "c2", "c1"], transport=transport) == {
        "c1": "Ravi S.",
        "c2": "Customer",
    }
    assert await names.fetch_display_names(["c1"], transport=transport) == {"c1": "Ravi S."}
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_the_lookup_degrades_to_customer(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", "k" * 40)
    monkeypatch.setattr(names, "_cache", {})

    def down(request):
        raise httpx.ConnectError("refused")

    assert await names.fetch_display_names(["c1"], transport=httpx.MockTransport(down)) == {"c1": "Customer"}
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", "")
    assert await names.fetch_display_names(["c1"]) == {"c1": "Customer"}


def test_booking_model_has_no_contact_columns():
    assert not CONTACT_FIELDS & set(Booking.__table__.columns.keys())
