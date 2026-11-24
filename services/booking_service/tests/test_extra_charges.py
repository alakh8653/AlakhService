"""An extra charge moves the price only when the customer agrees, and never once the booking is paid."""

import pytest
from fastapi import HTTPException
from sqlalchemy import update

from app.core.payments import get_open_payment_closer
from app.main import app
from app.models.booking import Booking
from tests.test_shop_bookings_api import SENT, SESSIONS, auth, client  # noqa: F401  (client is a fixture)

OWNER, CUSTOMER = auth("owner-1"), auth("c3")
BK = "bk-4"
URL = f"/api/v1/bookings/{BK}/extra-charges"
BODY = {"amount_cents": 50000, "reason": "New capacitor needed"}


async def set_fields(**values):
    async with SESSIONS["factory"]() as db:
        await db.execute(update(Booking).where(Booking.id == BK).values(**values))
        await db.commit()


@pytest.fixture
def paid_elsewhere():
    """Closing open payments: False means nothing has been paid, as in the tests below by default."""

    state = {"paid": False, "error": None, "calls": 0}

    async def close(booking_id):
        state["calls"] += 1
        if state["error"]:
            raise state["error"]
        return state["paid"]

    app.dependency_overrides[get_open_payment_closer] = lambda: close
    return state


async def ask(client, headers=OWNER, body=BODY):  # noqa: F811
    await set_fields(status="IN_PROGRESS")
    return await client.post(URL, json=body, headers=headers)


async def total(client):  # noqa: F811
    return (await client.get(f"/api/v1/bookings/{BK}", headers=CUSTOMER)).json()


@pytest.mark.asyncio
async def test_asking_does_not_move_the_price_and_the_customer_is_told(client, paid_elsewhere):  # noqa: F811
    before = (await total(client))["total_amount"]
    SENT.clear()
    resp = await ask(client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["total_amount"] == before
    assert (body["pending_extra_amount"], body["pending_extra_reason"]) == (50000, "New capacitor needed")
    event, people, data = SENT[-1]
    assert (event, people) == ("booking.extra_requested", [("c3", "customer")])
    assert (data["amount"], data["reason"]) == ("₹500", "New capacitor needed")


@pytest.mark.asyncio
async def test_approving_raises_the_price_once_and_tells_the_shop(client, paid_elsewhere):  # noqa: F811
    before = (await total(client))["total_amount"]
    charge = (await ask(client)).json()["pending_extra_id"]
    SENT.clear()
    resp = await client.post(f"{URL}/{charge}/approve", headers=CUSTOMER)
    assert resp.status_code == 200
    body = resp.json()
    assert (body["total_amount"], body["extra_amount"], body["pending_extra_id"]) == (before + 50000, 50000, None)
    assert paid_elsewhere["calls"] == 1
    event, people, _ = SENT[-1]
    assert event == "booking.extra_approved" and ("owner-1", "shop") in people
    # Approving again changes nothing.
    assert (await client.post(f"{URL}/{charge}/approve", headers=CUSTOMER)).status_code == 409
    assert (await total(client))["total_amount"] == before + 50000


@pytest.mark.asyncio
async def test_declining_keeps_the_price_and_the_shop_may_ask_again(client, paid_elsewhere):  # noqa: F811
    before = (await total(client))["total_amount"]
    charge = (await ask(client)).json()["pending_extra_id"]
    SENT.clear()
    resp = await client.post(f"{URL}/{charge}/decline", headers=CUSTOMER)
    assert resp.status_code == 200
    assert (resp.json()["total_amount"], resp.json()["pending_extra_id"]) == (before, None)
    assert SENT[-1][0] == "booking.extra_declined"
    assert (await client.post(URL, json=BODY, headers=OWNER)).status_code == 201


@pytest.mark.asyncio
async def test_only_the_customer_can_agree_not_the_shop_or_an_admin(client, paid_elsewhere):  # noqa: F811
    charge = (await ask(client)).json()["pending_extra_id"]
    before = (await total(client))["total_amount"]
    for who in (OWNER, auth("ops", "admin")):
        assert (await client.post(f"{URL}/{charge}/approve", headers=who)).status_code == 403
    assert (await client.post(f"{URL}/{charge}/approve", headers=auth("stranger"))).status_code == 404
    assert (await total(client))["total_amount"] == before


@pytest.mark.asyncio
async def test_the_customer_cannot_ask_and_a_stranger_cannot_see(client):  # noqa: F811
    assert (await ask(client, CUSTOMER)).status_code == 403
    assert (await client.get(URL, headers=auth("stranger"))).status_code == 404


@pytest.mark.asyncio
async def test_a_paid_or_prepaid_or_finished_booking_cannot_take_an_extra(client):  # noqa: F811
    await set_fields(payment_status="PAID")
    resp = await ask(client)
    assert resp.status_code == 409 and "already paid" in resp.json()["detail"]
    await set_fields(payment_status="UNPAID", metadata_json='{"package_purchase_id": "pkg-1"}')
    assert (await ask(client)).status_code == 409
    await set_fields(metadata_json=None, status="COMPLETED")
    assert (await client.post(URL, json=BODY, headers=OWNER)).status_code == 409
    await set_fields(status="IN_PROGRESS", customer_id="walk-in:1")
    assert (await client.post(URL, json=BODY, headers=OWNER)).status_code == 409


@pytest.mark.asyncio
async def test_payment_made_just_before_approving_wins_and_the_price_stays(client, paid_elsewhere):  # noqa: F811
    before = (await total(client))["total_amount"]
    charge = (await ask(client)).json()["pending_extra_id"]
    paid_elsewhere["paid"] = True
    resp = await client.post(f"{URL}/{charge}/approve", headers=CUSTOMER)
    assert resp.status_code == 409 and "just been paid" in resp.json()["detail"]
    after = await total(client)
    assert (after["total_amount"], after["pending_extra_id"]) == (before, None)


@pytest.mark.asyncio
async def test_payment_service_being_down_leaves_everything_as_it_was(client, paid_elsewhere):  # noqa: F811
    before = (await total(client))["total_amount"]
    charge = (await ask(client)).json()["pending_extra_id"]
    paid_elsewhere["error"] = HTTPException(status_code=503, detail="Please try again in a minute")
    assert (await client.post(f"{URL}/{charge}/approve", headers=CUSTOMER)).status_code == 503
    after = await total(client)
    assert (after["total_amount"], after["pending_extra_id"]) == (before, charge)


@pytest.mark.asyncio
async def test_a_request_left_unanswered_ends_with_the_booking(client, paid_elsewhere):  # noqa: F811
    charge = (await ask(client)).json()["pending_extra_id"]
    await set_fields(status="COMPLETED")
    # Nothing left to answer on screen, and answering anyway is refused.
    assert (await total(client))["pending_extra_id"] is None
    assert (await client.post(f"{URL}/{charge}/approve", headers=CUSTOMER)).status_code == 409


@pytest.mark.asyncio
async def test_one_request_at_a_time_and_the_shop_can_take_it_back(client, paid_elsewhere):  # noqa: F811
    charge = (await ask(client)).json()["pending_extra_id"]
    assert (await client.post(URL, json=BODY, headers=OWNER)).status_code == 409
    resp = await client.delete(f"{URL}/{charge}", headers=OWNER)
    assert (resp.status_code, resp.json()["pending_extra_id"]) == (200, None)
    assert (await client.post(f"{URL}/{charge}/approve", headers=CUSTOMER)).status_code == 409


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad",
    [
        {"amount_cents": 0, "reason": "Parts"},
        {"amount_cents": 100, "reason": " "},
        {"amount_cents": 50000001, "reason": "Parts"},
    ],
)
async def test_nonsense_is_refused(client, bad):  # noqa: F811
    assert (await ask(client, body=bad)).status_code == 422


@pytest.mark.asyncio
async def test_a_phone_number_in_the_reason_is_hidden_from_the_customer(client, paid_elsewhere):  # noqa: F811
    body = (await ask(client, body={"amount_cents": 100, "reason": "Parts, call 9876543210"})).json()
    assert "9876543210" not in body["pending_extra_reason"]
    assert "9876543210" not in (await total(client))["pending_extra_reason"]
    assert "9876543210" not in (await client.get(URL, headers=CUSTOMER)).json()[0]["reason"]


@pytest.mark.asyncio
async def test_asking_again_and_again_stops_after_five(client, paid_elsewhere):  # noqa: F811
    await set_fields(status="IN_PROGRESS")
    for _ in range(5):
        charge = (await client.post(URL, json=BODY, headers=OWNER)).json()["pending_extra_id"]
        assert (await client.delete(f"{URL}/{charge}", headers=OWNER)).status_code == 200
    SENT.clear()
    resp = await client.post(URL, json=BODY, headers=OWNER)
    assert resp.status_code == 409 and "Too many" in resp.json()["detail"]
    assert SENT == []
