"""Customers pay for their own bookings at the booked price; payments are private; refunds are admin-only."""
import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool, StaticPool

from app.config import settings
from app.database import Base, get_db
from app.dependencies import get_booking_lookup, get_redis, get_shop_owner_lookup
from app.main import app

TEST_DB = os.environ.get("TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:")

BOOKINGS = {
    "bk-1": {"id": "bk-1", "customer_id": "cust", "shop_id": "shop-1", "provider_id": None, "status": "CONFIRMED", "total_amount": 49900},
    "bk-new": {"id": "bk-new", "customer_id": "cust", "shop_id": "shop-1", "provider_id": None, "status": "PENDING", "total_amount": 100},
}
OWNERS = {"shop-1": "owner"}


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
