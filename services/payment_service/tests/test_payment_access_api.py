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
from app.core.razorpay import RazorpayGateway, get_razorpay
from app.database import Base, get_db
from app.dependencies import get_booking_lookup, get_redis, get_shop_owner_lookup
from app.main import app

TEST_DB = os.environ.get("TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:")

BOOKINGS = {
    "bk-1": {"id": "bk-1", "customer_id": "cust", "shop_id": "shop-1", "provider_id": None, "status": "CONFIRMED", "total_amount": 49900},
    "bk-new": {"id": "bk-new", "customer_id": "cust", "shop_id": "shop-1", "provider_id": None, "status": "PENDING", "total_amount": 100},
}
OWNERS = {"shop-1": "owner"}
KEY_SECRET = "rzp-secret"
WEBHOOK_SECRET = "rzp-webhook-secret"
ORDERS: list = []


def razorpay_api(request: httpx.Request) -> httpx.Response:
    """Stands in for Razorpay's Orders API."""
    assert request.url.path == "/v1/orders"
    assert request.headers["authorization"].startswith("Basic ")
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
    ORDERS.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_customers_pay_for_their_own_bookings_at_the_booked_price(client):
    body = {"booking_id": "bk-1", "payment_method": "upi", "idempotency_key": "key-0001",
            "amount_cents": 1, "payer_id": "someone", "payee_id": "attacker"}
    assert (await client.post("/api/v1/payments/initiate", json=body, headers=auth("stranger"))).status_code == 404
    assert (await client.post("/api/v1/payments/initiate", json={**body, "booking_id": "bk-new"}, headers=auth("cust"))).status_code == 409

    paid = await client.post("/api/v1/payments/initiate", json=body, headers=auth("cust"))
    assert paid.status_code == 201
    payment = paid.json()
    assert (payment["amount_cents"], payment["payer_id"], payment["payee_id"]) == (49900, "cust", "owner")

    # Retrying with the same key returns the same payment; nobody else can use the key to read it.
    assert (await client.post("/api/v1/payments/initiate", json=body, headers=auth("cust"))).json()["id"] == payment["id"]
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
        "gateway": "razorpay", "key_id": "rzp_test_key", "order_id": "order_1", "amount_cents": 49900, "currency": "INR",
    }
    assert ORDERS == [{"amount": 49900, "currency": "INR", "receipt": payment["id"][:40],
                       "notes": {"payment_id": payment["id"], "booking_id": "bk-1"}}]

    # A retry reuses the order instead of opening another.
    again = await client.post("/api/v1/payments/initiate", json=body, headers=auth("cust"))
    assert again.json()["checkout"]["order_id"] == "order_1"
    assert len(ORDERS) == 1

    url = f"/api/v1/payments/{payment['id']}/verify"
    proof = {"razorpay_order_id": "order_1", "razorpay_payment_id": "pay_1",
             "razorpay_signature": sign(KEY_SECRET, b"order_1|pay_1")}
    assert (await client.post(url, json={**proof, "razorpay_signature": "forged"}, headers=auth("cust"))).status_code == 400
    assert (await client.post(url, json={**proof, "razorpay_order_id": "order_9",
                                         "razorpay_signature": sign(KEY_SECRET, b"order_9|pay_1")}, headers=auth("cust"))).status_code == 400
    assert (await client.post(url, json=proof, headers=auth("stranger"))).status_code == 404

    done = await client.post(url, json=proof, headers=auth("cust"))
    assert done.status_code == 200
    assert (done.json()["status"], done.json()["checkout"]) == ("COMPLETED", None)
    # Confirming again is harmless (crediting once is covered in test_payments).
    assert (await client.post(url, json=proof, headers=auth("cust"))).json()["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_cash_needs_no_gateway_and_online_needs_one(client):
    app.dependency_overrides[get_razorpay] = lambda: RazorpayGateway()
    body = {"booking_id": "bk-1", "payment_method": "card", "idempotency_key": "key-0004"}
    refused = await client.post("/api/v1/payments/initiate", json=body, headers=auth("cust"))
    assert refused.status_code == 503

    cash = await client.post("/api/v1/payments/initiate", json={**body, "payment_method": "cash"}, headers=auth("cust"))
    assert cash.status_code == 201
    assert (cash.json()["status"], cash.json()["checkout"]) == ("PENDING", None)
    assert (await client.post("/api/v1/payments/initiate", json={**body, "payment_method": "bitcoin",
                                                                 "idempotency_key": "key-0005"}, headers=auth("cust"))).status_code == 422


@pytest.mark.asyncio
async def test_razorpay_webhooks_must_be_signed_with_the_webhook_secret(client):
    body = {"booking_id": "bk-1", "payment_method": "upi", "idempotency_key": "key-0006"}
    payment = (await client.post("/api/v1/payments/initiate", json=body, headers=auth("cust"))).json()

    def event(amount: int) -> bytes:
        return json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": {
            "id": "pay_9", "order_id": "order_1", "amount": amount, "currency": "INR", "notes": {}}}}}).encode()

    hook = "/api/v1/webhooks/razorpay"
    status = lambda: client.get(f"/api/v1/payments/{payment['id']}", headers=auth("cust"))  # noqa: E731

    assert (await client.post(hook, content=event(49900), headers={"x-razorpay-signature": "forged"})).status_code == 400
    # Signed with the API key secret instead of the webhook secret: still refused.
    assert (await client.post(hook, content=event(49900), headers={"x-razorpay-signature": sign(KEY_SECRET, event(49900))})).status_code == 400
    # Signed, but for a different amount: ignored.
    assert (await client.post(hook, content=event(1), headers={"x-razorpay-signature": sign(WEBHOOK_SECRET, event(1))})).status_code == 200
    assert (await status()).json()["status"] == "PENDING"

    ok = await client.post(hook, content=event(49900), headers={"x-razorpay-signature": sign(WEBHOOK_SECRET, event(49900))})
    assert ok.status_code == 200
    assert (await status()).json()["status"] == "COMPLETED"

    app.dependency_overrides[get_razorpay] = lambda: RazorpayGateway("k", "s")
    assert (await client.post(hook, content=event(49900), headers={"x-razorpay-signature": "x"})).status_code == 503


@pytest.mark.asyncio
async def test_stripe_webhook_is_refused_without_its_secret(client):
    forged = {"type": "payment_intent.succeeded", "data": {"object": {"id": "pi_1", "metadata": {"payment_id": "x"}}}}
    assert (await client.post("/api/v1/webhooks/stripe", json=forged)).status_code == 503
