"""Prepaid packages: shops offer them, customers buy them online, and each visit is booked and earned in turn."""

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio

from app.database import get_db
from app.dependencies import get_service_lookup
from app.main import app
from app.models.payment import PackagePurchase, Payment, ShopEarning
from tests import test_earnings_api
from tests.test_earnings_api import ADMIN, OWNER, cancel_body, internal, rows
from tests.test_payment_access_api import KEY_SECRET, NOTIFIED, REFUNDS, auth, sign

# The API client with the fakes for booking_service, shops and Razorpay (see test_earnings_api).
http = test_earnings_api.http
client = test_earnings_api.client
CUSTOMER = auth("cust")
SERVICES = {
    "svc-cut": {"id": "svc-cut", "shop_id": "shop-1", "name": "Haircut", "price_cents": 30000, "is_active": True},
    "svc-elsewhere": {
        "id": "svc-elsewhere",
        "shop_id": "shop-9",
        "name": "Facial",
        "price_cents": 50000,
        "is_active": True,
    },
}


@pytest_asyncio.fixture
async def shop(http):
    async def fake_service(service_id):
        return SERVICES.get(service_id)

    app.dependency_overrides[get_service_lookup] = lambda: fake_service
    yield http


async def offer(http, visits=5, price=120000, **extra):
    body = {
        "shop_id": "shop-1",
        "service_id": "svc-cut",
        "name": "5 haircuts",
        "visits": visits,
        "price_cents": price,
        "valid_days": 90,
        **extra,
    }
    resp = await http.post("/api/v1/packages", json=body, headers=OWNER)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def bought(http, package_id, key="pkg-key-1") -> str:
    resp = await http.post(
        f"/api/v1/packages/{package_id}/buy", json={"payment_method": "upi", "idempotency_key": key}, headers=CUSTOMER
    )
    assert resp.status_code == 201, resp.text
    payment = resp.json()["payment"]
    order = payment["checkout"]["order_id"]
    proof = {
        "razorpay_order_id": order,
        "razorpay_payment_id": f"pay_{key}",
        "razorpay_signature": sign(KEY_SECRET, f"{order}|pay_{key}".encode()),
    }
    assert (
        await http.post(f"/api/v1/payments/{payment['id']}/verify", json=proof, headers=CUSTOMER)
    ).status_code == 200
    return resp.json()["purchase_id"]


def use(http, purchase_id, booking_id, service="svc-cut", customer="cust"):
    body = {"customer_id": customer, "purchase_id": purchase_id, "service_id": service, "booking_id": booking_id}
    return internal(http, "/packages/redeem", body)


@pytest.mark.asyncio
async def test_only_the_owner_offers_packages_of_their_own_services(shop):
    package = await offer(shop)
    assert (package["visits"], package["price_cents"], package["is_active"]) == (5, 120000, True)
    body = {
        "shop_id": "shop-1",
        "service_id": "svc-cut",
        "name": "x deal",
        "visits": 3,
        "price_cents": 1000,
        "valid_days": 30,
    }
    assert (await shop.post("/api/v1/packages", json=body, headers=auth("stranger"))).status_code == 403
    other = {**body, "service_id": "svc-elsewhere"}
    assert (await shop.post("/api/v1/packages", json=other, headers=OWNER)).status_code == 422
    listed = (await shop.get("/api/v1/packages", params={"service_id": "svc-cut"})).json()
    assert [p["id"] for p in listed] == [package["id"]]

    off = await shop.patch(f"/api/v1/packages/{package['id']}", json={"is_active": False}, headers=OWNER)
    assert off.json()["is_active"] is False
    assert (await shop.get("/api/v1/packages", params={"shop_id": "shop-1"})).json() == []
    assert len((await shop.get("/api/v1/packages/shop/shop-1", headers=OWNER)).json()) == 1


@pytest.mark.asyncio
async def test_a_package_bought_online_is_invoiced_and_ready_to_use(shop):
    package = await offer(shop)
    NOTIFIED.clear()
    purchase_id = await bought(shop, package["id"])
    [mine] = (await shop.get("/api/v1/packages/mine", headers=CUSTOMER)).json()
    assert (mine["id"], mine["status"], mine["visits_left"], mine["usable"]) == (purchase_id, "ACTIVE", 5, True)
    [payment] = await rows(Payment, Payment.booking_id == purchase_id)
    assert (payment.purpose, payment.status, payment.amount_cents) == ("PACKAGE", "COMPLETED", 120000)
    assert payment.invoice_number is not None
    assert [e for e, _, _ in NOTIFIED] == ["payment.package"]
    assert (await shop.get("/api/v1/payments", headers=CUSTOMER)).json() == []  # not a booking's payment


@pytest.mark.asyncio
async def test_each_visit_is_booked_once_and_earned_when_completed(shop):
    purchase_id = await bought(shop, (await offer(shop))["id"])
    first = await use(shop, purchase_id, "bk-p1")
    assert first.json() == {"booking_id": "bk-p1", "visit_value_cents": 24000, "visits_left": 4}
    assert (await use(shop, purchase_id, "bk-p1")).json()["visits_left"] == 4  # the same booking again: once
    assert (await use(shop, purchase_id, "bk-x", service="svc-elsewhere")).status_code == 422
    assert (await use(shop, purchase_id, "bk-x", customer="someone")).status_code == 404

    done = await internal(
        shop, "/booking/bk-p1/completed", {"shop_id": "shop-1", "customer_id": "cust", "total_amount": 0}
    )
    earning = done.json()["earning"]
    assert (earning["collection"], earning["gross_cents"], earning["commission_cents"], earning["gst_cents"]) == (
        "ONLINE",
        24000,
        2400,
        432,
    )
    assert earning["payout_cents"] == 24000 - 2400 - 432

    await use(shop, purchase_id, "bk-p2")
    await internal(shop, "/booking/bk-p2/cancelled", cancel_body("customer", 48))
    [purchase] = await rows(PackagePurchase, PackagePurchase.id == purchase_id)
    assert purchase.visits_left == 4  # the cancelled booking's visit came back


@pytest.mark.asyncio
async def test_the_last_visit_takes_what_rounding_left(shop):
    purchase_id = await bought(shop, (await offer(shop, visits=3, price=100000))["id"])
    values = [(await use(shop, purchase_id, f"bk-{i}")).json()["visit_value_cents"] for i in range(3)]
    assert values == [33333, 33333, 33334] and sum(values) == 100000
    assert (await use(shop, purchase_id, "bk-4")).status_code == 409  # none left


@pytest.mark.asyncio
async def test_an_expired_package_cannot_be_used(shop):
    purchase_id = await bought(shop, (await offer(shop))["id"])
    gen = app.dependency_overrides[get_db]()
    db = await gen.__anext__()
    try:
        purchase = await db.get(PackagePurchase, purchase_id)
        purchase.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        await db.commit()
    finally:
        await gen.aclose()
    refused = await use(shop, purchase_id, "bk-late")
    assert refused.status_code == 409 and "expired" in refused.json()["detail"]


@pytest.mark.asyncio
async def test_an_admin_refunds_only_the_unused_visits(shop):
    purchase_id = await bought(shop, (await offer(shop))["id"])
    await use(shop, purchase_id, "bk-p1")
    await internal(shop, "/booking/bk-p1/completed", {"shop_id": "shop-1", "customer_id": "cust", "total_amount": 0})
    assert (await shop.post(f"/api/v1/admin/payments/packages/{purchase_id}/refund", headers=OWNER)).status_code == 403
    refunded = await shop.post(f"/api/v1/admin/payments/packages/{purchase_id}/refund", headers=ADMIN)
    assert refunded.status_code == 200, refunded.text
    assert (refunded.json()["status"], refunded.json()["visits_left"]) == ("REFUNDED", 0)
    assert [amount for _, amount in REFUNDS] == [96000]  # 4 of 5 visits
    [sale] = await rows(ShopEarning, ShopEarning.booking_id == "bk-p1")
    assert (sale.gross_cents, sale.status) == (24000, "READY")  # the visit already given stays earned
    assert (await use(shop, purchase_id, "bk-p9")).status_code == 409
