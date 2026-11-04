"""Before a booking's price changes, checkouts started at the old price are closed, and a paid booking says so."""

import uuid

import pytest

from app.database import get_db
from app.main import app
from app.models.payment import Payment
from tests.test_earnings_api import KEY, http, internal  # noqa: F401  (http is a fixture)
from tests.test_payment_access_api import client  # noqa: F401


async def payment(status, booking="bk-9", purpose="BOOKING"):
    gen = app.dependency_overrides[get_db]()
    db = await gen.__anext__()
    row = Payment(
        id=str(uuid.uuid4()),
        booking_id=booking,
        payer_id="c1",
        payee_id="owner",
        amount_cents=50000,
        currency="INR",
        status=status,
        payment_method="cash",
        purpose=purpose,
        idempotency_key=uuid.uuid4().hex,
    )
    db.add(row)
    await db.commit()
    await gen.aclose()
    return row.id


async def status_of(payment_id):
    gen = app.dependency_overrides[get_db]()
    db = await gen.__anext__()
    value = (await db.get(Payment, payment_id)).status
    await gen.aclose()
    return value


@pytest.mark.asyncio
async def test_a_checkout_at_the_old_price_is_closed(http):  # noqa: F811
    open_one = await payment("PENDING")
    other_booking = await payment("PENDING", booking="bk-10")
    resp = await internal(http, "/booking/bk-9/close-open")
    assert (resp.status_code, resp.json()) == (200, {"paid": False, "closed": 1})
    assert await status_of(open_one) == "FAILED"
    assert await status_of(other_booking) == "PENDING"


@pytest.mark.asyncio
async def test_a_paid_booking_says_so_and_nothing_is_closed(http):  # noqa: F811
    paid = await payment("COMPLETED")
    open_one = await payment("PENDING")
    resp = await internal(http, "/booking/bk-9/close-open")
    assert resp.json() == {"paid": True, "closed": 0}
    assert await status_of(paid) == "COMPLETED"
    assert await status_of(open_one) == "PENDING"


@pytest.mark.asyncio
async def test_only_other_services_may_ask(http):  # noqa: F811
    assert (await internal(http, "/booking/bk-9/close-open", key="wrong")).status_code in (401, 403)
    assert KEY
