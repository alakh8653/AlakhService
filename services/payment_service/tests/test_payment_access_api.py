"""Customers pay for their own bookings at the booked price; payments are private; refunds are admin-only."""

import hashlib
import hmac
import json
import os

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool, StaticPool

from app.config import settings
from app.core.notifier import get_notifier
from app.core.razorpay import RazorpayGateway, get_razorpay
from app.database import Base, get_db
from app.dependencies import get_booking_lookup, get_redis, get_shop_owner_lookup
from app.main import app

TEST_DB = os.environ.get("TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:")

BOOKINGS = {
    "bk-1": {
        "id": "bk-1",
        "customer_id": "cust",
        "shop_id": "shop-1",
        "provider_id": None,
        "status": "CONFIRMED",
        "total_amount": 49900,
    },
    "bk-2": {
        "id": "bk-2",
        "customer_id": "cust",
        "shop_id": "shop-1",
        "provider_id": None,
        "status": "CONFIRMED",
        "total_amount": 20000,
    },
    "bk-new": {
        "id": "bk-new",
        "customer_id": "cust",
        "shop_id": "shop-1",
        "provider_id": None,
        "status": "PENDING",
        "total_amount": 100,
    },
}
OWNERS = {"shop-1": "owner"}
KEY_SECRET = "rzp-secret"
WEBHOOK_SECRET = "rzp-webhook-secret"
ORDERS: list = []
NOTIFIED: list = []


class RecordingNotifier:
    async def send(self, event, recipients, data):
        NOTIFIED.append((event, [(r["user_id"], r["role"]) for r in recipients], data["amount"]))


REFUNDS: list = []
REFUSE_REFUNDS: list = []


def razorpay_api(request: httpx.Request) -> httpx.Response:
    """Stands in for Razorpay's Orders and Refunds APIs."""
    assert request.headers["authorization"].startswith("Basic ")
    if request.url.path.endswith("/refund"):
        if REFUSE_REFUNDS:
            return httpx.Response(400, json={"error": {"description": "The amount is invalid"}})
        refund = json.loads(request.content)
        REFUNDS.append((request.url.path, refund["amount"]))
        return httpx.Response(200, json={"id": f"rfnd_{len(REFUNDS)}", "status": "processed", **refund})
    assert request.url.path == "/v1/orders"
    order = json.loads(request.content)
    ORDERS.append(order)
    return httpx.Response(200, json={"id": f"order_{len(ORDERS)}", **order})


def fake_gateway() -> RazorpayGateway:
    return RazorpayGateway("rzp_test_key", KEY_SECRET, WEBHOOK_SECRET, transport=httpx.MockTransport(razorpay_api))


def sign(secret: str, message: bytes) -> str:
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def auth(sub: str, role: str = "user") -> dict:
    token = jwt.encode({"sub": sub, "role": role, "type": "access"}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {"Authorization": f"Bearer {token}"}


class FakeRedis:
    def __init__(self):
        self.store = {}

    async def get(self, key):
        return self.store.get(key)

    async def setex(self, key, ttl, value):
        self.store[key] = value


@pytest_asyncio.fixture
async def client():
    engine = create_async_engine(TEST_DB, poolclass=StaticPool if ":memory:" in TEST_DB else NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    redis = FakeRedis()

    async def override_get_db():
        async with factory() as session:
            yield session
            await session.commit()

    async def override_redis():
        yield redis

    async def fake_booking(booking_id, token):
        # booking_service only shows a booking to its parties; here only its customer asks.
        booking = BOOKINGS.get(booking_id)
        caller = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])["sub"]
        return booking if booking and caller == booking["customer_id"] else None

    async def fake_owner(shop_id):
        return OWNERS.get(shop_id)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_redis
    app.dependency_overrides[get_booking_lookup] = lambda: fake_booking
    app.dependency_overrides[get_shop_owner_lookup] = lambda: fake_owner
    app.dependency_overrides[get_razorpay] = fake_gateway
    app.dependency_overrides[get_notifier] = RecordingNotifier
    ORDERS.clear()
    NOTIFIED.clear()
    REFUNDS.clear()
    REFUSE_REFUNDS.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_customers_pay_for_their_own_bookings_at_the_booked_price(client):
    body = {
        "booking_id": "bk-1",
        "payment_method": "upi",
        "idempotency_key": "key-0001",
        "amount_cents": 1,
        "payer_id": "someone",
        "payee_id": "attacker",
    }
    assert (await client.post("/api/v1/payments/initiate", json=body, headers=auth("stranger"))).status_code == 404
    assert (
        await client.post("/api/v1/payments/initiate", json={**body, "booking_id": "bk-new"}, headers=auth("cust"))
    ).status_code == 409

    paid = await client.post("/api/v1/payments/initiate", json=body, headers=auth("cust"))
    assert paid.status_code == 201
    payment = paid.json()
    assert (payment["amount_cents"], payment["payer_id"], payment["payee_id"]) == (49900, "cust", "owner")

    # Retrying with the same key returns the same payment; nobody else can use the key to read it.
    assert (await client.post("/api/v1/payments/initiate", json=body, headers=auth("cust"))).json()["id"] == payment[
        "id"
    ]
    assert (await client.post("/api/v1/payments/initiate", json=body, headers=auth("stranger"))).status_code == 404


@pytest.mark.asyncio
async def test_payments_are_private_and_refunds_admin_only(client):
    body = {"booking_id": "bk-1", "payment_method": "upi", "idempotency_key": "key-0002"}
    payment = (await client.post("/api/v1/payments/initiate", json=body, headers=auth("cust"))).json()
    url = f"/api/v1/payments/{payment['id']}"
    assert (await client.get(url, headers=auth("cust"))).status_code == 200
    assert (await client.get(url, headers=auth("owner"))).status_code == 200
    assert (await client.get(url, headers=auth("stranger"))).status_code == 404
    assert (await client.get(url, headers=auth("ops", "admin"))).status_code == 200

    refund = {"amount_cents": 49900, "reason": "x"}
    for who in ("cust", "owner", "stranger"):
        assert (await client.post(f"{url}/refund", json=refund, headers=auth(who))).status_code == 403

    assert (await client.get("/api/v1/accounts/owner/balance", headers=auth("stranger"))).status_code == 404
    assert (await client.get("/api/v1/accounts/owner/balance", headers=auth("owner"))).status_code == 200
    assert (await client.get("/api/v1/accounts/owner/transactions", headers=auth("cust"))).status_code == 404


@pytest.mark.asyncio
async def test_online_payment_opens_a_razorpay_order_and_completes_only_with_a_valid_signature(client):
    body = {"booking_id": "bk-1", "payment_method": "upi", "idempotency_key": "key-0003"}
    started = await client.post("/api/v1/payments/initiate", json=body, headers=auth("cust"))
    assert started.status_code == 201
    payment = started.json()
    assert payment["status"] == "PENDING"
    assert payment["checkout"] == {
        "gateway": "razorpay",
        "key_id": "rzp_test_key",
        "order_id": "order_1",
        "amount_cents": 49900,
        "currency": "INR",
    }
    assert ORDERS == [
        {
            "amount": 49900,
            "currency": "INR",
            "receipt": payment["id"][:40],
            "notes": {"payment_id": payment["id"], "booking_id": "bk-1"},
        }
    ]

    # A retry reuses the order instead of opening another.
    again = await client.post("/api/v1/payments/initiate", json=body, headers=auth("cust"))
    assert again.json()["checkout"]["order_id"] == "order_1"
    assert len(ORDERS) == 1

    url = f"/api/v1/payments/{payment['id']}/verify"
    proof = {
        "razorpay_order_id": "order_1",
        "razorpay_payment_id": "pay_1",
        "razorpay_signature": sign(KEY_SECRET, b"order_1|pay_1"),
    }
    assert (
        await client.post(url, json={**proof, "razorpay_signature": "forged"}, headers=auth("cust"))
    ).status_code == 400
    assert (
        await client.post(
            url,
            json={**proof, "razorpay_order_id": "order_9", "razorpay_signature": sign(KEY_SECRET, b"order_9|pay_1")},
            headers=auth("cust"),
        )
    ).status_code == 400
    assert (await client.post(url, json=proof, headers=auth("stranger"))).status_code == 404

    done = await client.post(url, json=proof, headers=auth("cust"))
    assert done.status_code == 200
    assert (done.json()["status"], done.json()["checkout"]) == ("COMPLETED", None)
    # Confirming again is harmless (crediting once is covered in test_payments) and tells nobody twice.
    assert (await client.post(url, json=proof, headers=auth("cust"))).json()["status"] == "COMPLETED"
    assert NOTIFIED == [("payment.completed", [("cust", "customer"), ("owner", "shop")], "499.00")]


@pytest.mark.asyncio
async def test_cash_needs_no_gateway_and_online_needs_one(client):
    app.dependency_overrides[get_razorpay] = lambda: RazorpayGateway()
    body = {"booking_id": "bk-1", "payment_method": "card", "idempotency_key": "key-0004"}
    refused = await client.post("/api/v1/payments/initiate", json=body, headers=auth("cust"))
    assert refused.status_code == 503

    cash = await client.post("/api/v1/payments/initiate", json={**body, "payment_method": "cash"}, headers=auth("cust"))
    assert cash.status_code == 201
    assert (cash.json()["status"], cash.json()["checkout"]) == ("PENDING", None)
    assert (
        await client.post(
            "/api/v1/payments/initiate",
            json={**body, "payment_method": "bitcoin", "idempotency_key": "key-0005"},
            headers=auth("cust"),
        )
    ).status_code == 422


@pytest.mark.asyncio
async def test_razorpay_webhooks_must_be_signed_with_the_webhook_secret(client):
    body = {"booking_id": "bk-1", "payment_method": "upi", "idempotency_key": "key-0006"}
    payment = (await client.post("/api/v1/payments/initiate", json=body, headers=auth("cust"))).json()

    def event(amount: int) -> bytes:
        return json.dumps(
            {
                "event": "payment.captured",
                "payload": {
                    "payment": {
                        "entity": {
                            "id": "pay_9",
                            "order_id": "order_1",
                            "amount": amount,
                            "currency": "INR",
                            "notes": {},
                        }
                    }
                },
            }
        ).encode()

    hook = "/api/v1/webhooks/razorpay"
    status = lambda: client.get(f"/api/v1/payments/{payment['id']}", headers=auth("cust"))  # noqa: E731

    assert (
        await client.post(hook, content=event(49900), headers={"x-razorpay-signature": "forged"})
    ).status_code == 400
    # Signed with the API key secret instead of the webhook secret: still refused.
    assert (
        await client.post(hook, content=event(49900), headers={"x-razorpay-signature": sign(KEY_SECRET, event(49900))})
    ).status_code == 400
    # Signed, but for a different amount: ignored.
    assert (
        await client.post(hook, content=event(1), headers={"x-razorpay-signature": sign(WEBHOOK_SECRET, event(1))})
    ).status_code == 200
    assert (await status()).json()["status"] == "PENDING"

    assert NOTIFIED == []
    ok = await client.post(
        hook, content=event(49900), headers={"x-razorpay-signature": sign(WEBHOOK_SECRET, event(49900))}
    )
    assert ok.status_code == 200
    assert (await status()).json()["status"] == "COMPLETED"
    assert [e for e, _, _ in NOTIFIED] == ["payment.completed"]
    # Razorpay retries webhooks; a repeat changes and announces nothing.
    await client.post(hook, content=event(49900), headers={"x-razorpay-signature": sign(WEBHOOK_SECRET, event(49900))})
    assert len(NOTIFIED) == 1

    app.dependency_overrides[get_razorpay] = lambda: RazorpayGateway("k", "s")
    assert (await client.post(hook, content=event(49900), headers={"x-razorpay-signature": "x"})).status_code == 503


@pytest.mark.asyncio
async def test_stripe_webhook_is_refused_without_its_secret(client):
    forged = {"type": "payment_intent.succeeded", "data": {"object": {"id": "pi_1", "metadata": {"payment_id": "x"}}}}
    assert (await client.post("/api/v1/webhooks/stripe", json=forged)).status_code == 503


async def paid_by_razorpay(client, key: str, booking: str = "bk-1") -> str:
    body = {"booking_id": booking, "payment_method": "upi", "idempotency_key": key}
    payment = (await client.post("/api/v1/payments/initiate", json=body, headers=auth("cust"))).json()
    order = payment["checkout"]["order_id"]
    proof = {
        "razorpay_order_id": order,
        "razorpay_payment_id": "pay_77",
        "razorpay_signature": sign(KEY_SECRET, f"{order}|pay_77".encode()),
    }
    assert (
        await client.post(f"/api/v1/payments/{payment['id']}/verify", json=proof, headers=auth("cust"))
    ).status_code == 200
    return payment["id"]


@pytest.mark.asyncio
async def test_refunds_go_back_through_razorpay_up_to_what_was_paid(client):
    pid = await paid_by_razorpay(client, "key-0010")
    url, ops = f"/api/v1/payments/{pid}/refund", auth("ops", "admin")
    status = lambda: client.get(f"/api/v1/payments/{pid}", headers=ops)  # noqa: E731

    first = await client.post(url, json={"amount_cents": 10_000, "reason": "late"}, headers=ops)
    assert (first.status_code, first.json()["status"], first.json()["gateway_refund_id"]) == (
        200,
        "PROCESSED",
        "rfnd_1",
    )
    assert REFUNDS == [("/v1/payments/pay_77/refund", 10_000)]
    assert (await status()).json()["status"] == "PARTIALLY_REFUNDED"
    assert NOTIFIED[-1] == ("payment.refunded", [("cust", "customer")], "100.00")

    # Never more than was paid, across refunds.
    too_much = await client.post(url, json={"amount_cents": 40_000, "reason": "x"}, headers=ops)
    assert too_much.status_code == 400 and "left to refund" in too_much.json()["detail"]
    rest = await client.post(url, json={"amount_cents": 39_900, "reason": "cancelled"}, headers=ops)
    assert rest.json()["status"] == "PROCESSED"
    assert (await status()).json()["status"] == "REFUNDED"
    assert (await client.post(url, json={"amount_cents": 1, "reason": "x"}, headers=ops)).status_code == 400


@pytest.mark.asyncio
async def test_a_refund_razorpay_refuses_is_not_recorded(client):
    pid = await paid_by_razorpay(client, "key-0011")
    REFUSE_REFUNDS.append(True)
    resp = await client.post(
        f"/api/v1/payments/{pid}/refund", json={"amount_cents": 100, "reason": "x"}, headers=auth("ops", "admin")
    )
    assert resp.status_code == 502
    assert (await client.get(f"/api/v1/payments/{pid}", headers=auth("cust"))).json()["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_a_failed_refund_puts_the_payment_back(client):
    pid = await paid_by_razorpay(client, "key-0012")
    ops = auth("ops", "admin")
    await client.post(f"/api/v1/payments/{pid}/refund", json={"amount_cents": 49_900, "reason": "x"}, headers=ops)
    event = json.dumps(
        {"event": "refund.failed", "payload": {"refund": {"entity": {"id": "rfnd_1", "payment_id": "pay_77"}}}}
    ).encode()
    hook = await client.post(
        "/api/v1/webhooks/razorpay", content=event, headers={"x-razorpay-signature": sign(WEBHOOK_SECRET, event)}
    )
    assert hook.status_code == 200
    assert (await client.get(f"/api/v1/payments/{pid}", headers=ops)).json()["status"] == "COMPLETED"
    # ...so it can be refunded again.
    assert (
        await client.post(
            f"/api/v1/payments/{pid}/refund", json={"amount_cents": 49_900, "reason": "retry"}, headers=ops
        )
    ).status_code == 200


@pytest.mark.asyncio
async def test_payments_for_a_booking_are_listed_to_its_parties_and_admins(client):
    pid = await paid_by_razorpay(client, "key-0013")

    def listed(who, role="user"):
        return client.get("/api/v1/payments", params={"booking_id": "bk-1"}, headers=auth(who, role))

    assert [p["id"] for p in (await listed("ops", "admin")).json()] == [pid]
    assert [p["id"] for p in (await listed("cust")).json()] == [pid]
    assert [p["id"] for p in (await listed("owner")).json()] == [pid]
    assert (await listed("stranger")).json() == []


@pytest.mark.asyncio
async def test_the_shop_confirms_cash_and_it_can_then_be_refunded(client):
    body = {"booking_id": "bk-1", "payment_method": "cash", "idempotency_key": "key-0014"}
    pid = (await client.post("/api/v1/payments/initiate", json=body, headers=auth("cust"))).json()["id"]
    url = f"/api/v1/payments/{pid}/cash-received"
    assert (await client.post(url, headers=auth("stranger"))).status_code == 404
    assert (
        await client.post(url, headers=auth("cust"))
    ).status_code == 403  # the payer can't mark their own cash received

    done = await client.post(url, headers=auth("owner"))
    assert (done.status_code, done.json()["status"], done.json()["gateway"]) == (200, "COMPLETED", "cash")
    assert NOTIFIED[-1][:2] == ("payment.completed", [("cust", "customer"), ("owner", "shop")])
    assert (await client.post(url, headers=auth("owner"))).status_code == 409

    refund = await client.post(
        f"/api/v1/payments/{pid}/refund", json={"amount_cents": 49_900, "reason": "x"}, headers=auth("ops", "admin")
    )
    assert refund.json()["status"] == "MANUAL"
    assert REFUNDS == []  # nothing sent to Razorpay for cash

    upi = await paid_by_razorpay(client, "key-0015", booking="bk-2")
    assert (await client.post(f"/api/v1/payments/{upi}/cash-received", headers=auth("owner"))).status_code == 409


@pytest.mark.asyncio
async def test_a_booking_is_paid_for_once(client):
    cash = (
        await client.post(
            "/api/v1/payments/initiate",
            json={"booking_id": "bk-1", "payment_method": "cash", "idempotency_key": "key-0020"},
            headers=auth("cust"),
        )
    ).json()
    pid = await paid_by_razorpay(client, "key-0021")
    # Paying online made the earlier cash choice moot.
    assert (await client.get(f"/api/v1/payments/{cash['id']}", headers=auth("cust"))).json()["status"] == "CANCELLED"

    again = await client.post(
        "/api/v1/payments/initiate",
        json={"booking_id": "bk-1", "payment_method": "upi", "idempotency_key": "key-0022"},
        headers=auth("cust"),
    )
    assert (again.status_code, again.json()["detail"]) == (409, "This booking has already been paid for")
    # The original attempt's retry still answers with its payment.
    retry = await client.post(
        "/api/v1/payments/initiate",
        json={"booking_id": "bk-1", "payment_method": "upi", "idempotency_key": "key-0021"},
        headers=auth("cust"),
    )
    assert (retry.status_code, retry.json()["id"]) == (201, pid)

    mine = (await client.get("/api/v1/payments", headers=auth("cust"))).json()
    assert {p["id"]: p["status"] for p in mine} == {pid: "COMPLETED", cash["id"]: "CANCELLED"}
    assert (await client.get("/api/v1/payments", headers=auth("stranger"))).json() == []


async def open_checkout(client, key: str, booking: str = "bk-1") -> tuple[str, dict]:
    """Starts an online payment; returns it with the proof Razorpay's checkout would hand the app once paid."""
    body = {"booking_id": booking, "payment_method": "upi", "idempotency_key": key}
    payment = (await client.post("/api/v1/payments/initiate", json=body, headers=auth("cust"))).json()
    order = payment["checkout"]["order_id"]
    proof = {
        "razorpay_order_id": order,
        "razorpay_payment_id": f"pay_{key}",
        "razorpay_signature": sign(KEY_SECRET, f"{order}|pay_{key}".encode()),
    }
    return payment["id"], proof


async def razorpay_captured(client, pid: str, proof: dict, amount: int = 49900):
    entity = {
        "id": proof["razorpay_payment_id"],
        "order_id": proof["razorpay_order_id"],
        "amount": amount,
        "currency": "INR",
        "notes": {"payment_id": pid},
    }
    event = json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": entity}}}).encode()
    return await client.post(
        "/api/v1/webhooks/razorpay", content=event, headers={"x-razorpay-signature": sign(WEBHOOK_SECRET, event)}
    )


@pytest.mark.asyncio
async def test_a_replayed_confirmation_never_reopens_a_refunded_payment(client):
    ops = auth("ops", "admin")
    status = lambda pid: client.get(f"/api/v1/payments/{pid}", headers=ops)  # noqa: E731
    escrows = lambda: client.get("/api/v1/finance/settlements", headers=ops)  # noqa: E731

    pid, proof = await open_checkout(client, "key-0030")
    verify = lambda: client.post(f"/api/v1/payments/{pid}/verify", json=proof, headers=auth("cust"))  # noqa: E731
    await verify()
    await client.post(f"/api/v1/payments/{pid}/refund", json={"amount_cents": 49_900, "reason": "x"}, headers=ops)
    notified, settled = len(NOTIFIED), (await escrows()).json()

    replay = await verify()
    assert (replay.status_code, replay.json()["status"]) == (200, "REFUNDED")
    await razorpay_captured(client, pid, proof)
    assert (await status(pid)).json()["status"] == "REFUNDED"
    assert (await escrows()).json() == settled
    assert len(NOTIFIED) == notified

    partly, proof = await open_checkout(client, "key-0031", booking="bk-2")
    await client.post(f"/api/v1/payments/{partly}/verify", json=proof, headers=auth("cust"))
    await client.post(f"/api/v1/payments/{partly}/refund", json={"amount_cents": 100, "reason": "x"}, headers=ops)
    await client.post(f"/api/v1/payments/{partly}/verify", json=proof, headers=auth("cust"))
    await razorpay_captured(client, partly, proof, amount=20000)
    assert (await status(partly)).json()["status"] == "PARTIALLY_REFUNDED"


@pytest.mark.asyncio
async def test_a_confirmation_for_a_failed_payment_does_not_complete_it(client):
    pid, proof = await open_checkout(client, "key-0032")
    entity = {"id": "pay_x", "order_id": proof["razorpay_order_id"], "notes": {"payment_id": pid}}
    failed = json.dumps({"event": "payment.failed", "payload": {"payment": {"entity": entity}}}).encode()
    await client.post(
        "/api/v1/webhooks/razorpay", content=failed, headers={"x-razorpay-signature": sign(WEBHOOK_SECRET, failed)}
    )
    verified = await client.post(f"/api/v1/payments/{pid}/verify", json=proof, headers=auth("cust"))
    assert (verified.status_code, verified.json()["status"]) == (200, "FAILED")
    assert [e for e, _, _ in NOTIFIED] == ["payment.failed"]


@pytest.mark.asyncio
async def test_a_second_checkout_paid_for_the_same_booking_is_refunded(client):
    first, first_proof = await open_checkout(client, "key-0040")
    second, second_proof = await open_checkout(client, "key-0041")  # e.g. a retry in another tab
    await client.post(f"/api/v1/payments/{first}/verify", json=first_proof, headers=auth("cust"))

    late = await client.post(f"/api/v1/payments/{second}/verify", json=second_proof, headers=auth("cust"))
    assert (late.status_code, late.json()["status"]) == (200, "REFUNDED")
    assert REFUNDS == [("/v1/payments/pay_key-0041/refund", 49900)]
    assert NOTIFIED[-1] == ("payment.refunded", [("cust", "customer")], "499.00")
    pays = (await client.get("/api/v1/payments", params={"booking_id": "bk-1"}, headers=auth("cust"))).json()
    assert {p["id"]: p["status"] for p in pays} == {first: "COMPLETED", second: "REFUNDED"}

    # Razorpay's webhook for the same capture, or a replayed confirmation, refunds nothing more.
    await razorpay_captured(client, second, second_proof)
    await client.post(f"/api/v1/payments/{second}/verify", json=second_proof, headers=auth("cust"))
    assert len(REFUNDS) == 1
    # The duplicate never reached escrow; the booking's own payment is held as usual.
    escrows = (await client.get("/api/v1/finance/settlements", headers=auth("ops", "admin"))).json()
    assert {s["payment_id"]: s["status"] for s in escrows["data"]} == {first: "HELD", second: "CREATED"}


@pytest.mark.asyncio
async def test_a_duplicate_razorpay_will_not_refund_is_left_for_an_admin_to_refund(client):
    first, first_proof = await open_checkout(client, "key-0042")
    second, second_proof = await open_checkout(client, "key-0043")
    await client.post(f"/api/v1/payments/{first}/verify", json=first_proof, headers=auth("cust"))
    REFUSE_REFUNDS.append(True)
    await razorpay_captured(client, second, second_proof)
    ops = auth("ops", "admin")
    assert (await client.get(f"/api/v1/payments/{second}", headers=ops)).json()["status"] == "DUPLICATE"

    REFUSE_REFUNDS.clear()
    url = f"/api/v1/payments/{second}/refund"
    assert (await client.post(url, json={"amount_cents": 100, "reason": "x"}, headers=ops)).status_code == 400
    refund = await client.post(url, json={"amount_cents": 49_900, "reason": "paid twice"}, headers=ops)
    assert (refund.status_code, refund.json()["status"]) == (200, "PROCESSED")
    assert REFUNDS == [("/v1/payments/pay_key-0043/refund", 49900)]
    pays = (await client.get("/api/v1/payments", params={"booking_id": "bk-1"}, headers=ops)).json()
    assert {p["id"]: p["status"] for p in pays} == {first: "COMPLETED", second: "REFUNDED"}

    # If that refund fails after all, the payment is a duplicate again, not a second completed payment.
    event = json.dumps({"event": "refund.failed", "payload": {"refund": {"entity": {"id": "rfnd_1"}}}}).encode()
    await client.post(
        "/api/v1/webhooks/razorpay", content=event, headers={"x-razorpay-signature": sign(WEBHOOK_SECRET, event)}
    )
    assert (await client.get(f"/api/v1/payments/{second}", headers=ops)).json()["status"] == "DUPLICATE"


@pytest.mark.asyncio
async def test_customers_see_their_own_balance_and_history(client):
    pid, proof = await open_checkout(client, "key-0050")
    await client.post(f"/api/v1/payments/{pid}/verify", json=proof, headers=auth("cust"))
    await client.post(
        f"/api/v1/payments/{pid}/refund", json={"amount_cents": 10_000, "reason": "late"}, headers=auth("ops", "admin")
    )

    balance = await client.get("/api/v1/accounts/cust/balance", headers=auth("cust"))
    assert balance.json() == {"account_id": "cust", "balance_cents": 10_000}
    history = (await client.get("/api/v1/accounts/cust/transactions", headers=auth("cust"))).json()
    assert (history["total"], history["items"][0]["amount_cents"]) == (1, 10_000)

    # The account can also be named by its own id (as admins do); it stays private to its owner.
    account_id = history["items"][0]["account_id"]
    for who, role in (("cust", "user"), ("ops", "admin")):
        named = await client.get(f"/api/v1/accounts/{account_id}/balance", headers=auth(who, role))
        assert named.json()["balance_cents"] == 10_000
    assert (await client.get(f"/api/v1/accounts/{account_id}/balance", headers=auth("owner"))).status_code == 404
    assert (await client.get(f"/api/v1/accounts/{account_id}/transactions", headers=auth("owner"))).status_code == 404

    # Someone whose money has not moved yet sees an empty account rather than an error.
    assert (await client.get("/api/v1/accounts/owner/balance", headers=auth("owner"))).json()["balance_cents"] == 0
    assert (await client.get("/api/v1/accounts/owner/transactions", headers=auth("owner"))).json()["total"] == 0
