"""Completed bookings earn their shop money less commission; payouts, cancel refunds, disputes, invoices."""

import json
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.config import settings
from app.core import risk
from app.core.audit import get_audit_reporter
from app.core.peers import get_booking_sync, get_shop_directory
from app.database import get_db
from app.main import app
from app.models.payment import Escrow, Payment, ShopEarning
from tests.test_payment_access_api import (  # noqa: F401  (client is a fixture)
    REFUNDS,
    REFUSE_REFUNDS,
    WEBHOOK_SECRET,
    auth,
    client,
    paid_by_razorpay,
    sign,
)

KEY = "k" * 40
SYNCED: list = []
AUDITED: list = []
SHOPS = {"shop-1": {"id": "shop-1", "name": "Ravi Salon", "gstin": "29ABCDE1234F1Z5", "address": "MG Road"}}
PAYOUT_DETAILS = {
    "shop-1": {"method": "BANK", "account_name": "Ravi", "account_number": "001122", "ifsc": "HDFC0001"},
    "shop-3": {"method": "UPI", "account_name": "=HYPERLINK(1)", "upi_id": "x@upi"},
}
ADMIN = auth("ops", "admin")
OWNER = auth("owner")


class FakeSync:
    async def payment_status(self, booking_id, status, attempts=3):
        SYNCED.append((booking_id, status))
        return True


class FakeShops:
    async def shop(self, shop_id):
        return SHOPS.get(shop_id)

    async def payout_details(self, shop_id):
        return PAYOUT_DETAILS.get(shop_id)


class FakeAudit:
    async def record(self, actor, action, kind, rid, origin, **kw):
        AUDITED.append((action, rid))


@pytest_asyncio.fixture
async def http(client, monkeypatch):  # noqa: F811
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", KEY)

    async def no_risk(*a, **k):
        return None

    monkeypatch.setattr(risk, "report_risk", no_risk)
    app.dependency_overrides[get_booking_sync] = FakeSync
    app.dependency_overrides[get_shop_directory] = FakeShops
    app.dependency_overrides[get_audit_reporter] = FakeAudit
    SYNCED.clear()
    AUDITED.clear()
    yield client


async def internal(http, path: str, body: dict | None = None, key: str = KEY):
    return await http.post(f"/internal/payments{path}", json=body or {}, headers={"X-Internal-Key": key})


async def rows(model, *where):
    gen = app.dependency_overrides[get_db]()
    db = await gen.__anext__()
    try:
        return list((await db.execute(select(model).where(*where))).scalars().all())
    finally:
        await gen.aclose()


def today():
    return datetime.now(timezone.utc).date().isoformat()


@pytest.mark.asyncio
async def test_internal_routes_need_the_key(http):
    assert (await internal(http, "/booking/bk-1/completed", key="wrong")).status_code == 401
    assert (await http.post("/internal/payments/booking/bk-1/completed", json={})).status_code == 401


@pytest.mark.asyncio
async def test_a_completed_online_booking_releases_escrow_less_commission_once(http):
    pid = await paid_by_razorpay(http, "key-earn-1")
    assert ("bk-1", "PAID") in SYNCED

    first = await internal(http, "/booking/bk-1/completed", {"shop_id": "shop-1", "total_amount": 49900})
    assert first.status_code == 200
    assert first.json()["created"] is True
    assert first.json()["earning"] == {
        "booking_id": "bk-1",
        "shop_id": "shop-1",
        "collection": "ONLINE",
        "gross_cents": 49900,
        "commission_cents": 4990,
        "gst_cents": 898,
        "net_cents": 44012,
        "payout_cents": 44012,
        "status": "READY",
    }
    again = await internal(http, "/booking/bk-1/completed", {"shop_id": "shop-1", "total_amount": 49900})
    assert again.json()["created"] is False
    assert len(await rows(ShopEarning)) == 1
    assert [e.status for e in await rows(Escrow, Escrow.payment_id == pid)] == ["RELEASED"]

    url = f"/api/v1/payments/shops/shop-1/earnings?from={today()}&to={today()}"
    report = (await http.get(url, headers=OWNER)).json()
    assert (report["gross"], report["commission"], report["gst_on_commission"], report["net"]) == (
        499.0,
        49.9,
        8.98,
        440.12,
    )
    assert (report["pending_payout"], report["paid_out"], report["currency"]) == (440.12, 0, "INR")
    assert report["items"][0]["payment_id"] == pid
    assert report["items"][0]["payout_status"] == "READY"
    assert (await http.get(url, headers=auth("stranger"))).status_code == 404
    assert (await http.get(url, headers=ADMIN)).status_code == 200


@pytest.mark.asyncio
async def test_cash_commission_is_netted_against_the_next_payout(http):
    # bk-2 was paid at the shop (never through us): the shop owes 10% + GST of ₹200.
    cash = await internal(http, "/booking/bk-2/completed", {"shop_id": "shop-1", "total_amount": 20000})
    assert (cash.json()["earning"]["collection"], cash.json()["earning"]["payout_cents"]) == ("CASH", -2360)

    # On its own that is no payout: the debt waits for the next batch.
    empty = await http.post("/api/v1/admin/payments/payouts/batches", json={"period_to": today()}, headers=ADMIN)
    assert (empty.status_code, empty.json()["payouts"]) == (201, [])

    await paid_by_razorpay(http, "key-earn-2")
    await internal(http, "/booking/bk-1/completed", {"shop_id": "shop-1"})
    batch = (
        await http.post("/api/v1/admin/payments/payouts/batches", json={"period_to": today()}, headers=ADMIN)
    ).json()
    assert [(p["shop_id"], p["amount_cents"], p["status"]) for p in batch["payouts"]] == [
        ("shop-1", 44012 - 2360, "PENDING")
    ]
    payout_id = batch["payouts"][0]["id"]
    # Already in a batch: a second batch does not pay it again.
    again = await http.post("/api/v1/admin/payments/payouts/batches", json={"period_to": today()}, headers=ADMIN)
    assert again.json()["payouts"] == []

    paid = await http.post(
        f"/api/v1/admin/payments/payouts/{payout_id}/mark-paid", json={"reference": "UTR123"}, headers=ADMIN
    )
    assert (paid.status_code, paid.json()["status"], paid.json()["reference"]) == (200, "PAID", "UTR123")
    repeat = await http.post(
        f"/api/v1/admin/payments/payouts/{payout_id}/mark-paid", json={"reference": "UTR123"}, headers=ADMIN
    )
    assert repeat.status_code == 200
    other = await http.post(
        f"/api/v1/admin/payments/payouts/{payout_id}/mark-paid", json={"reference": "UTR999"}, headers=ADMIN
    )
    assert other.status_code == 409
    assert {e.status for e in await rows(ShopEarning)} == {"PAID"}
    assert ("mark_payout_paid", payout_id) in AUDITED

    mine = (await http.get("/api/v1/payments/shops/shop-1/payouts", headers=OWNER)).json()
    assert [(p["amount"], p["status"], p["reference"]) for p in mine] == [(416.52, "PAID", "UTR123")]
    listed = (await http.get("/api/v1/admin/payments/payouts?status=PAID", headers=ADMIN)).json()
    assert listed["total"] == 1
    assert (await http.get("/api/v1/admin/payments/payouts", headers=OWNER)).status_code == 403


@pytest.mark.asyncio
async def test_a_payment_after_a_cash_settlement_becomes_an_online_earning(http):
    await internal(http, "/booking/bk-1/completed", {"shop_id": "shop-1", "total_amount": 49900})
    await paid_by_razorpay(http, "key-earn-late")  # the customer paid in the app afterwards
    [sale] = await rows(ShopEarning)
    assert (sale.collection, sale.payout_cents) == ("ONLINE", 44012)


@pytest.mark.asyncio
async def test_commission_override_per_shop(http):
    base = "/api/v1/admin/payments/commission"
    assert (await http.get(base, headers=OWNER)).status_code == 403
    assert (await http.get(f"{base}/shop-1", headers=ADMIN)).json() == {
        "shop_id": "shop-1",
        "commission_percent": 10.0,
        "gst_on_commission_percent": 18.0,
        "source": "default",
    }
    assert (await http.put(f"{base}/shop-1", json={"commission_percent": 80}, headers=ADMIN)).status_code == 422
    set_ = await http.put(f"{base}/shop-1", json={"commission_percent": 5}, headers=ADMIN)
    assert (set_.json()["commission_percent"], set_.json()["source"]) == (5.0, "shop")
    listing = (await http.get(base, headers=ADMIN)).json()
    assert [(o["shop_id"], o["commission_percent"]) for o in listing["overrides"]] == [("shop-1", 5.0)]

    done = await internal(http, "/booking/bk-2/completed", {"shop_id": "shop-1", "total_amount": 20000})
    assert done.json()["earning"]["commission_cents"] == 1000  # 5%

    # The default applies to shops without their own rate; null goes back to the configured one.
    await http.put(base, json={"commission_percent": 12.5}, headers=ADMIN)
    assert (await http.get(f"{base}/shop-9", headers=ADMIN)).json()["commission_percent"] == 12.5
    await http.put(f"{base}/shop-1", json={"commission_percent": None}, headers=ADMIN)
    assert (await http.get(f"{base}/shop-1", headers=ADMIN)).json()["commission_percent"] == 12.5
    await http.put(base, json={"commission_percent": None}, headers=ADMIN)
    assert (await http.get(base, headers=ADMIN)).json()["default_commission_percent"] == 10.0


def cancel_body(by: str, hours_from_now: float) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "cancelled_by": by,
        "scheduled_at": (now + timedelta(hours=hours_from_now)).isoformat(),
        "cancelled_at": now.isoformat(),
    }


@pytest.mark.asyncio
async def test_cancel_refunds_in_full_once(http):
    pid = await paid_by_razorpay(http, "key-cancel-1")
    SYNCED.clear()
    first = await internal(http, "/booking/bk-1/cancelled", cancel_body("customer", 1))  # late, but fee is 0
    assert first.status_code == 200
    assert (first.json()["status"], first.json()["refund_cents"], first.json()["fee_cents"]) == ("refunded", 49900, 0)
    assert REFUNDS == [("/v1/payments/pay_77/refund", 49900)]
    assert SYNCED == [("bk-1", "REFUNDED")]
    again = await internal(http, "/booking/bk-1/cancelled", cancel_body("customer", 1))
    assert again.json()["status"] == "already_refunded"
    assert len(REFUNDS) == 1
    [payment] = await rows(Payment, Payment.id == pid)
    assert payment.status == "REFUNDED"


@pytest.mark.asyncio
async def test_a_late_customer_cancel_keeps_the_fee_for_the_shop(http, monkeypatch):
    monkeypatch.setattr(settings, "CANCEL_FEE_PERCENT", 10)
    await paid_by_razorpay(http, "key-cancel-2")
    out = (await internal(http, "/booking/bk-1/cancelled", cancel_body("customer", 1))).json()
    assert (out["refund_cents"], out["fee_cents"], out["payment_status"]) == (44910, 4990, "PARTIALLY_REFUNDED")
    [fee] = await rows(ShopEarning)
    assert (fee.gross_cents, fee.commission_cents, fee.gst_cents) == (4990, 499, 90)


@pytest.mark.asyncio
@pytest.mark.parametrize("by, hours", [("customer", 3), ("shop", 0.5), ("admin", 0.5)])
async def test_in_time_or_shop_and_admin_cancels_refund_everything(http, monkeypatch, by, hours):
    monkeypatch.setattr(settings, "CANCEL_FEE_PERCENT", 50)
    await paid_by_razorpay(http, f"key-cancel-{by}")
    out = (await internal(http, "/booking/bk-1/cancelled", cancel_body(by, hours))).json()
    assert (out["refund_cents"], out["fee_cents"]) == (49900, 0)


@pytest.mark.asyncio
async def test_a_razorpay_failure_leaves_the_cancel_to_be_retried(http):
    await paid_by_razorpay(http, "key-cancel-3")
    REFUSE_REFUNDS.append(True)
    assert (await internal(http, "/booking/bk-1/cancelled", cancel_body("shop", 5))).status_code == 502
    REFUSE_REFUNDS.clear()
    retried = await internal(http, "/booking/bk-1/cancelled", cancel_body("shop", 5))
    assert retried.json()["status"] == "refunded"


@pytest.mark.asyncio
async def test_an_unpaid_cancel_closes_open_checkouts_and_refunds_a_late_capture(http):
    body = {"booking_id": "bk-1", "payment_method": "upi", "idempotency_key": "key-cancel-4"}
    payment = (await http.post("/api/v1/payments/initiate", json=body, headers=auth("cust"))).json()
    out = (await internal(http, "/booking/bk-1/cancelled", cancel_body("customer", 5))).json()
    assert out["status"] == "nothing_to_refund"
    # The customer finishes paying after all: the money goes straight back.
    entity = {
        "id": "pay_late",
        "order_id": payment["checkout"]["order_id"],
        "amount": 49900,
        "currency": "INR",
        "notes": {"payment_id": payment["id"]},
    }
    event = json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": entity}}}).encode()
    hook = await http.post(
        "/api/v1/webhooks/razorpay", content=event, headers={"x-razorpay-signature": sign(WEBHOOK_SECRET, event)}
    )
    assert hook.status_code == 200
    assert REFUNDS == [("/v1/payments/pay_late/refund", 49900)]
    [p] = await rows(Payment, Payment.id == payment["id"])
    assert p.status == "REFUNDED"


@pytest.mark.asyncio
async def test_a_dispute_holds_the_earning_and_a_partial_refund_shrinks_it(http):
    await paid_by_razorpay(http, "key-dispute-1")
    await internal(http, "/booking/bk-1/completed", {"shop_id": "shop-1"})
    held = await internal(http, "/booking/bk-1/disputed")
    assert held.json()["earning"]["status"] == "HELD"
    batch = await http.post("/api/v1/admin/payments/payouts/batches", json={"period_to": today()}, headers=ADMIN)
    assert batch.json()["payouts"] == []

    body = {"amount_cents": 10000, "reason": "Partly done", "idempotency_key": "dispute:d-1"}
    refund = await internal(http, "/booking/bk-1/refund", body)
    assert (refund.status_code, refund.json()["refund_cents"]) == (200, 10000)
    again = await internal(http, "/booking/bk-1/refund", body)
    assert again.json()["refund_id"] == refund.json()["refund_id"]
    assert REFUNDS == [("/v1/payments/pay_77/refund", 10000)]
    assert SYNCED[-1] == ("bk-1", "PARTIALLY_REFUNDED")
    [sale] = await rows(ShopEarning)
    assert (sale.gross_cents, sale.commission_cents, sale.gst_cents, sale.status) == (39900, 3990, 718, "READY")

    too_much = {"amount_cents": 50000, "reason": "x", "idempotency_key": "dispute:d-2"}
    assert (await internal(http, "/booking/bk-1/refund", too_much)).status_code == 422
    rest = await internal(http, "/booking/bk-1/refund", {"reason": "All of it", "idempotency_key": "dispute:d-3"})
    assert rest.json()["refund_cents"] == 39900
    [sale] = await rows(ShopEarning)
    assert (sale.gross_cents, sale.payout_cents, sale.status) == (0, 0, "REFUNDED")
    assert (await internal(http, "/booking/bk-1/refund", too_much | {"idempotency_key": "x" * 9})).status_code == 409


@pytest.mark.asyncio
async def test_release_to_shop_after_a_dispute(http):
    await paid_by_razorpay(http, "key-dispute-2")
    # Disputed before it was completed: nothing recorded yet, so releasing settles it now.
    assert (await internal(http, "/booking/bk-1/disputed")).json()["earning"] is None
    released = await internal(http, "/booking/bk-1/release")
    assert released.json()["earning"]["status"] == "READY"
    assert released.json()["earning"]["payout_cents"] == 44012
    assert (await internal(http, "/booking/bk-x/release")).json()["earning"] is None


@pytest.mark.asyncio
async def test_a_refund_after_the_payout_comes_off_the_next_one(http):
    await paid_by_razorpay(http, "key-dispute-3")
    await internal(http, "/booking/bk-1/completed", {"shop_id": "shop-1"})
    batch = (
        await http.post("/api/v1/admin/payments/payouts/batches", json={"period_to": today()}, headers=ADMIN)
    ).json()
    await http.post(
        f"/api/v1/admin/payments/payouts/{batch['payouts'][0]['id']}/mark-paid",
        json={"reference": "UTR1"},
        headers=ADMIN,
    )
    await internal(http, "/booking/bk-1/refund", {"amount_cents": 10000, "reason": "x", "idempotency_key": "dsp:abc1"})
    [adjustment] = await rows(ShopEarning, ShopEarning.kind == "ADJUSTMENT")
    # Net on ₹399 is 35192; the shop was paid 44012.
    assert (adjustment.gross_cents, adjustment.payout_cents, adjustment.status) == (-10000, 35192 - 44012, "READY")


@pytest.mark.asyncio
async def test_invoices_are_numbered_in_order_and_shown_to_the_parties(http):
    first = await paid_by_razorpay(http, "key-inv-1")
    second = await paid_by_razorpay(http, "key-inv-2", booking="bk-2")
    [p1] = await rows(Payment, Payment.id == first)
    [p2] = await rows(Payment, Payment.id == second)
    fy = p1.invoice_number.split("/")[1]
    assert p1.invoice_number == f"ALK/{fy}/000001"
    assert p2.invoice_number == f"ALK/{fy}/000002"

    page = await http.get(f"/api/v1/payments/{first}/invoice", headers=auth("cust"))
    assert page.status_code == 200
    assert page.headers["content-type"].startswith("text/html")
    html = page.text
    assert p1.invoice_number in html
    assert settings.PLATFORM_GSTIN in html
    assert "29ABCDE1234F1Z5" in html and "Ravi Salon" in html
    assert "₹499.00" in html and "₹49.90" in html and "₹8.98" in html
    assert (await http.get(f"/api/v1/payments/{first}/invoice", headers=OWNER)).status_code == 200
    assert (await http.get(f"/api/v1/payments/{first}/invoice", headers=ADMIN)).status_code == 200
    assert (await http.get(f"/api/v1/payments/{first}/invoice", headers=auth("stranger"))).status_code == 404

    # shop_service unreachable or without a GSTIN: still an invoice, honest about it.
    SHOPS.pop("shop-1")
    try:
        html = (await http.get(f"/api/v1/payments/{first}/invoice", headers=auth("cust"))).text
    finally:
        SHOPS["shop-1"] = {"id": "shop-1", "name": "Ravi Salon", "gstin": "29ABCDE1234F1Z5", "address": "MG Road"}
    assert "not a tax invoice for the shop" in html


@pytest.mark.asyncio
async def test_no_invoice_before_payment_completes(http):
    body = {"booking_id": "bk-1", "payment_method": "cash", "idempotency_key": "key-inv-cash"}
    pid = (await http.post("/api/v1/payments/initiate", json=body, headers=auth("cust"))).json()["id"]
    assert (await http.get(f"/api/v1/payments/{pid}/invoice", headers=auth("cust"))).status_code == 409


@pytest.mark.asyncio
async def test_payout_csv_has_the_shops_details(http):
    await paid_by_razorpay(http, "key-csv-1")
    await internal(http, "/booking/bk-1/completed", {"shop_id": "shop-1"})
    for booking, shop in (("bk-b", "shop-2"), ("bk-c", "shop-3")):
        await internal(http, f"/booking/{booking}/completed", {"shop_id": shop, "total_amount": 1000})
    # Those two were paid at the shop; treat them as online so the shops are owed something.
    gen = app.dependency_overrides[get_db]()
    db = await gen.__anext__()
    for e in (await db.execute(select(ShopEarning).where(ShopEarning.shop_id != "shop-1"))).scalars().all():
        e.collection, e.payout_cents = "ONLINE", e.net_cents
    await db.commit()
    await gen.aclose()

    batch = await http.post("/api/v1/admin/payments/payouts/batches", json={"period_to": today()}, headers=ADMIN)
    assert len(batch.json()["payouts"]) == 3
    csv_resp = await http.get(
        f"/api/v1/admin/payments/payouts/export.csv?batch_id={batch.json()['batch_id']}", headers=ADMIN
    )
    assert csv_resp.status_code == 200
    assert csv_resp.headers["content-type"].startswith("text/csv")
    lines = csv_resp.text.strip().splitlines()
    assert lines[0].startswith("payout_id,batch_id,shop_id,amount")
    by_shop = {line.split(",")[2]: line for line in lines[1:]}
    assert "001122" in by_shop["shop-1"] and "HDFC0001" in by_shop["shop-1"]
    assert "Payout details missing" in by_shop["shop-2"]
    assert "'=HYPERLINK(1)" in by_shop["shop-3"]  # never run as a formula
