"""Quotes and history are the customer's own; coupons are created by admins."""

import json

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models.pricing  # noqa: F401  (registers the models on Base.metadata)
from app.config import settings
from app.core.audit import AuditReporter, get_audit_reporter
from app.database import Base, get_db
from app.main import app


def auth(sub: str, role: str = "user", token_type: str = "access") -> dict:
    token = jwt.encode(
        {"sub": sub, "role": role, "type": token_type}, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return {"Authorization": f"Bearer {token}"}


ALICE, BOB, ADMIN = auth("alice"), auth("bob"), auth("ops", "admin")
INTERNAL = {"X-Internal-Key": "test-internal-key"}


def redeem(client, quote_id: str, headers=INTERNAL):
    return client.post(f"/internal/pricing/{quote_id}/redeem", headers=headers)


@pytest_asyncio.fixture
async def client(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", INTERNAL["X-Internal-Key"])
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            yield session
            await session.commit()

    app.dependency_overrides[get_db] = override_get_db
    # No audit reports leave the tests unless a test asks for them (the internal key is set here).
    app.dependency_overrides[get_audit_reporter] = lambda: AuditReporter("http://admin", "")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_pricing_rules(client):
    quote = {"service_id": "s1", "customer_id": "bob", "base_price_cents": 10000}
    assert (await client.post("/api/v1/pricing/calculate", json=quote)).status_code == 401
    assert (await client.post("/api/v1/pricing/calculate", json=quote, headers=ALICE)).status_code == 403
    assert (
        await client.post("/api/v1/pricing/calculate", json={**quote, "customer_id": "alice"}, headers=ALICE)
    ).status_code == 201
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
    redeemed = await redeem(client, first)
    assert redeemed.status_code == 200 and redeemed.json()["redeemed_at"]
    assert (await redeem(client, first)).status_code == 409  # quote spent
    assert (await redeem(client, quotes[1]["id"])).status_code == 409  # one use each
    assert (await redeem(client, "missing")).status_code == 404

    bob = (await quote("bob")).json()
    assert (await redeem(client, bob["id"])).status_code == 200
    carol = (await quote("carol")).json()
    assert carol["coupon_code"] is None  # max_uses reached, so no discount is quoted
    assert (await client.get("/api/v1/coupons/TWICE/validate", headers=ALICE)).json()["is_valid"] is False


@pytest.mark.asyncio
async def test_admins_list_coupons_and_codes_are_case_insensitive(client):
    assert (
        await client.post("/api/v1/coupons", json={"code": " diwali25 ", "discount_pct": 0.25}, headers=ADMIN)
    ).json()["code"] == "DIWALI25"
    assert (
        await client.post("/api/v1/coupons", json={"code": "BAD", "discount_pct": 0.9}, headers=ADMIN)
    ).status_code == 422
    assert [c["code"] for c in (await client.get("/api/v1/coupons", headers=ADMIN)).json()] == ["DIWALI25"]
    assert (await client.get("/api/v1/coupons", headers=ALICE)).status_code == 403
    assert (await client.get("/api/v1/coupons/diwali25/validate", headers=ALICE)).json()["is_valid"] is True
    missing = await client.get("/api/v1/coupons/NOPE/validate", headers=ALICE)
    assert (missing.status_code, missing.json()["detail"]) == (404, "Coupon not found")


@pytest.mark.asyncio
async def test_customers_cannot_use_up_coupons_without_booking(client):
    await client.post("/api/v1/coupons", json={"code": "ONCE", "discount_pct": 0.5, "max_uses": 1}, headers=ADMIN)
    body = {"service_id": "anything", "customer_id": "alice", "base_price_cents": 1, "coupon_code": "ONCE"}
    quote = (await client.post("/api/v1/pricing/calculate", json=body, headers=ALICE)).json()

    # Redeeming is booking_service's job (checkout), never a customer's or a browser's.
    assert (await client.post(f"/api/v1/pricing/{quote['id']}/redeem", headers=ALICE)).status_code == 404
    assert (await redeem(client, quote["id"], headers=ALICE)).status_code == 401
    assert (await redeem(client, quote["id"], headers=ADMIN)).status_code == 401
    assert (await redeem(client, quote["id"], headers={"X-Internal-Key": "guess"})).status_code == 401
    assert (await client.get("/api/v1/coupons/ONCE/validate", headers=BOB)).json()["is_valid"] is True


@pytest.mark.asyncio
async def test_redeeming_is_refused_when_no_internal_key_is_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", "")
    assert (await redeem(client, "any", headers={"X-Internal-Key": ""})).status_code == 503


def admin_service_api(reports: list, status: int = 201, fail: bool = False) -> httpx.MockTransport:
    """Stands in for admin_service's POST /internal/audit-logs."""

    def handler(request: httpx.Request) -> httpx.Response:
        if fail:
            raise httpx.ConnectError("admin_service is down")
        assert request.url.path == "/internal/audit-logs"
        reports.append((request.headers["x-internal-key"], json.loads(request.content)))
        return httpx.Response(status)

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_coupons_admins_create_are_reported_to_the_audit_log(client):
    reports: list = []
    app.dependency_overrides[get_audit_reporter] = lambda: AuditReporter(
        "http://admin", "audit-key", transport=admin_service_api(reports)
    )
    origin = {"X-Real-IP": "203.0.113.5", "User-Agent": "AdminDashboard/2.0"}
    body = {"code": " summer10 ", "discount_pct": 0.1, "max_uses": 100}
    created = await client.post("/api/v1/coupons", json=body, headers={**ADMIN, **origin})
    assert created.status_code == 201
    # Customers cannot create coupons, so there is nothing to report.
    assert (await client.post("/api/v1/coupons", json=body, headers=ALICE)).status_code == 403

    assert reports == [
        (
            "audit-key",
            {
                "admin_id": "ops",
                "action": "create_coupon",
                "resource_type": "coupon",
                "resource_id": created.json()["id"],
                "old_values": None,
                "new_values": created.json(),
                "ip_address": "203.0.113.5",
                "user_agent": "AdminDashboard/2.0",
                "service": "pricing_engine",
            },
        )
    ]
    assert reports[0][1]["new_values"]["code"] == "SUMMER10"


@pytest.mark.asyncio
@pytest.mark.parametrize("broken", [{"status": 500}, {"fail": True}])
async def test_a_failing_admin_service_never_stops_a_coupon_being_created(client, broken):
    app.dependency_overrides[get_audit_reporter] = lambda: AuditReporter(
        "http://admin", "audit-key", transport=admin_service_api([], **broken)
    )
    created = await client.post("/api/v1/coupons", json={"code": "WINTER", "discount_pct": 0.2}, headers=ADMIN)
    assert created.status_code == 201
    assert [c["code"] for c in (await client.get("/api/v1/coupons", headers=ADMIN)).json()] == ["WINTER"]
