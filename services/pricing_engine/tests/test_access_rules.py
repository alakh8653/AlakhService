"""Quotes and history are the customer's own; coupons are created by admins."""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models.pricing  # noqa: F401  (registers the models on Base.metadata)
from app.config import settings
from app.database import Base, get_db
from app.main import app


def auth(sub: str, role: str = "user", token_type: str = "access") -> dict:
    token = jwt.encode({"sub": sub, "role": role, "type": token_type}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {"Authorization": f"Bearer {token}"}


ALICE, BOB, ADMIN = auth("alice"), auth("bob"), auth("ops", "admin")


@pytest_asyncio.fixture
async def client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            yield session
            await session.commit()

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_pricing_rules(client):
    quote = {"service_id": "s1", "customer_id": "bob", "base_price_cents": 10000}
    assert (await client.post("/api/v1/pricing/calculate", json=quote)).status_code == 401
    assert (await client.post("/api/v1/pricing/calculate", json=quote, headers=ALICE)).status_code == 403
    assert (await client.post("/api/v1/pricing/calculate", json={**quote, "customer_id": "alice"}, headers=ALICE)).status_code == 201
    assert (await client.get("/api/v1/pricing/history/bob", headers=ALICE)).status_code == 403
    assert (await client.get("/api/v1/pricing/history/alice", headers=ALICE)).status_code == 200

    coupon = {"code": "HALFOFF", "discount_pct": 0.5}
    assert (await client.post("/api/v1/coupons", json=coupon, headers=ALICE)).status_code == 403
    assert (await client.post("/api/v1/coupons", json=coupon, headers=ADMIN)).status_code == 201


@pytest.mark.asyncio
async def test_quotes_do_not_use_up_coupons_redeeming_does(client):
    await client.post("/api/v1/coupons", json={"code": "TWICE", "discount_pct": 0.10, "max_uses": 2}, headers=ADMIN)

    def quote(customer):
        body = {"service_id": "s1", "customer_id": customer, "base_price_cents": 10000, "coupon_code": "TWICE"}
        return client.post("/api/v1/pricing/calculate", json=body, headers=auth(customer))

    # Asking for prices many times never exhausts the coupon.
    quotes = [(await quote("alice")).json() for _ in range(5)]
    assert all(q["coupon_code"] == "TWICE" and q["redeemed_at"] is None for q in quotes)
    assert (await client.get("/api/v1/coupons/TWICE/validate", headers=ALICE)).json()["is_valid"] is True

    first = quotes[0]["id"]
    assert (await client.post(f"/api/v1/pricing/{first}/redeem", headers=BOB)).status_code == 404  # not Bob's quote
    redeemed = await client.post(f"/api/v1/pricing/{first}/redeem", headers=ALICE)
    assert redeemed.status_code == 200 and redeemed.json()["redeemed_at"]
    assert (await client.post(f"/api/v1/pricing/{first}/redeem", headers=ALICE)).status_code == 409  # quote spent
    assert (await client.post(f"/api/v1/pricing/{quotes[1]['id']}/redeem", headers=ALICE)).status_code == 409  # one use each

    bob = (await quote("bob")).json()
    assert (await client.post(f"/api/v1/pricing/{bob['id']}/redeem", headers=BOB)).status_code == 200
    carol = (await quote("carol")).json()
    assert carol["coupon_code"] is None  # max_uses reached, so no discount is quoted
    assert (await client.get("/api/v1/coupons/TWICE/validate", headers=ALICE)).json()["is_valid"] is False


@pytest.mark.asyncio
async def test_admins_list_coupons_and_codes_are_case_insensitive(client):
    assert (await client.post("/api/v1/coupons", json={"code": " diwali25 ", "discount_pct": 0.25}, headers=ADMIN)).json()["code"] == "DIWALI25"
    assert (await client.post("/api/v1/coupons", json={"code": "BAD", "discount_pct": 0.9}, headers=ADMIN)).status_code == 422
    assert [c["code"] for c in (await client.get("/api/v1/coupons", headers=ADMIN)).json()] == ["DIWALI25"]
    assert (await client.get("/api/v1/coupons", headers=ALICE)).status_code == 403
    assert (await client.get("/api/v1/coupons/diwali25/validate", headers=ALICE)).json()["is_valid"] is True
    missing = await client.get("/api/v1/coupons/NOPE/validate", headers=ALICE)
    assert (missing.status_code, missing.json()["detail"]) == (404, "Coupon not found")
