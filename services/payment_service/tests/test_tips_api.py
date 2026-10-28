"""Customers tip the provider of a completed booking: paid online, passed on in full with the next payout."""

import pytest

from app.models.payment import Payment, ShopEarning
from tests import test_earnings_api
from tests.test_earnings_api import ADMIN, OWNER, SYNCED, internal, rows, today
from tests.test_payment_access_api import BOOKINGS, KEY_SECRET, NOTIFIED, REFUNDS, auth, paid_by_razorpay, sign

# The API client with the fakes for booking_service, shops and Razorpay (see test_earnings_api).
http = test_earnings_api.http
client = test_earnings_api.client
CUSTOMER = auth("cust")


@pytest.fixture(autouse=True)
def done_booking():
    BOOKINGS["bk-done"] = {
        "id": "bk-done",
        "customer_id": "cust",
        "shop_id": "shop-1",
        "provider_id": "staff-1",
        "status": "COMPLETED",
        "total_amount": 49900,
    }
    yield
    BOOKINGS.pop("bk-done", None)


def start_tip(http, amount=5000, key="tip-key-1", booking="bk-done", who=CUSTOMER):
    body = {"booking_id": booking, "amount_cents": amount, "payment_method": "upi", "idempotency_key": key}
    return http.post("/api/v1/payments/tips", json=body, headers=who)


async def paid_tip(http, amount=5000, key="tip-key-1") -> str:
    resp = await start_tip(http, amount, key)
    assert resp.status_code == 201, resp.text
    tip = resp.json()
    order = tip["checkout"]["order_id"]
    proof = {
        "razorpay_order_id": order,
        "razorpay_payment_id": f"pay_{key}",
        "razorpay_signature": sign(KEY_SECRET, f"{order}|pay_{key}".encode()),
    }
    assert (await http.post(f"/api/v1/payments/{tip['id']}/verify", json=proof, headers=CUSTOMER)).status_code == 200
    return tip["id"]


@pytest.mark.asyncio
async def test_a_tip_goes_to_the_provider_in_full_with_no_invoice(http):
    await paid_by_razorpay(http, "key-booking-1", "bk-done")
    await internal(http, "/booking/bk-done/completed", {"shop_id": "shop-1", "total_amount": 49900})
    NOTIFIED.clear()
    SYNCED.clear()

    tip_id = await paid_tip(http)
    [tip] = await rows(Payment, Payment.id == tip_id)
    assert (tip.purpose, tip.status, tip.invoice_number) == ("TIP", "COMPLETED", None)
    [earning] = await rows(ShopEarning, ShopEarning.kind == "TIP")
    assert (earning.gross_cents, earning.commission_cents, earning.gst_cents, earning.payout_cents) == (
        5000,
        0,
        0,
        5000,
    )
    assert (earning.provider_id, earning.status, earning.shop_id) == ("staff-1", "READY", "shop-1")
    [sale] = await rows(ShopEarning, ShopEarning.kind == "SALE")
    assert sale.gross_cents == 49900  # the booking's own earning is untouched
    assert SYNCED == [("bk-done", "PAID")]  # still paid once, by its own payment

    [(event, recipients, amount)] = NOTIFIED
    assert (event, amount) == ("payment.tip", "50.00")
    assert sorted(recipients) == [("cust", "customer"), ("owner", "shop"), ("staff-1", "provider")]

    report = (
        await http.get(f"/api/v1/payments/shops/shop-1/earnings?from={today()}&to={today()}", headers=OWNER)
    ).json()
    assert report["tips"] == 50.0
    assert report["tips_by_provider"] == [{"provider_id": "staff-1", "amount": 50.0}]
    assert report["pending_payout"] == 440.12 + 50.0


@pytest.mark.asyncio
async def test_tips_are_kept_apart_from_the_bookings_own_payment(http):
    # Paid at the shop, then tipped, then paid online after all: none of them is taken for a duplicate.
    await internal(http, "/booking/bk-done/completed", {"shop_id": "shop-1", "total_amount": 49900})
    tip_id = await paid_tip(http)
    booking_payment = await paid_by_razorpay(http, "key-booking-2", "bk-done")
    statuses = {p.id: (p.purpose, p.status) for p in await rows(Payment)}
    assert statuses == {tip_id: ("TIP", "COMPLETED"), booking_payment: ("BOOKING", "COMPLETED")}
    assert REFUNDS == []

    own = (await http.get("/api/v1/payments", params={"booking_id": "bk-done"}, headers=CUSTOMER)).json()
    assert [p["id"] for p in own] == [booking_payment]
    tips = (
        await http.get("/api/v1/payments", params={"booking_id": "bk-done", "purpose": "TIP"}, headers=CUSTOMER)
    ).json()
    assert [(p["id"], p["purpose"]) for p in tips] == [(tip_id, "TIP")]
    mine = (await http.get("/api/v1/payments", headers=CUSTOMER)).json()
    assert tip_id not in [p["id"] for p in mine]  # the app's "paid?" check sees bookings only


@pytest.mark.asyncio
async def test_only_the_customer_tips_once_a_completed_booking_within_the_limits(http):
    assert (await start_tip(http, booking="bk-1")).status_code == 409  # still confirmed
    assert (await start_tip(http, who=auth("stranger"))).status_code == 404
    assert (await start_tip(http, amount=500)).status_code == 422  # under Rs 10
    assert (await start_tip(http, amount=300000)).status_code == 422  # over Rs 2,000
    cash = {"booking_id": "bk-done", "amount_cents": 5000, "payment_method": "cash", "idempotency_key": "tip-cash-1"}
    assert (await http.post("/api/v1/payments/tips", json=cash, headers=CUSTOMER)).status_code == 422

    await paid_tip(http)
    assert (await start_tip(http, key="tip-key-2")).status_code == 409  # tipped already
    again = await start_tip(http)  # the same request retried returns the same tip
    assert again.status_code == 201 and again.json()["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_tips_are_paid_out_and_a_refund_after_that_comes_off_the_next_payout(http):
    tip_id = await paid_tip(http)
    batch = (
        await http.post("/api/v1/admin/payments/payouts/batches", json={"period_to": today()}, headers=ADMIN)
    ).json()
    [payout] = batch["payouts"]
    assert payout["amount_cents"] == 5000
    await http.post(
        f"/api/v1/admin/payments/payouts/{payout['id']}/mark-paid", json={"reference": "UTR9"}, headers=ADMIN
    )

    refund = await http.post(
        f"/api/v1/payments/{tip_id}/refund", json={"amount_cents": 2000, "reason": "Tipped too much"}, headers=ADMIN
    )
    assert refund.status_code == 200, refund.text
    [adjustment] = await rows(ShopEarning, ShopEarning.kind == "TIP_ADJUSTMENT")
    assert (adjustment.gross_cents, adjustment.payout_cents, adjustment.provider_id) == (-2000, -2000, "staff-1")
    [sale_tip] = await rows(ShopEarning, ShopEarning.kind == "TIP")
    assert sale_tip.status == "PAID"


@pytest.mark.asyncio
async def test_a_tip_refunded_before_the_payout_is_no_longer_owed(http):
    tip_id = await paid_tip(http)
    await http.post(
        f"/api/v1/payments/{tip_id}/refund", json={"amount_cents": 5000, "reason": "Mistake"}, headers=ADMIN
    )
    [tip] = await rows(ShopEarning, ShopEarning.kind == "TIP")
    assert (tip.gross_cents, tip.payout_cents, tip.status) == (0, 0, "REFUNDED")
