"""Finance report API: settlements (escrow) and daily revenue."""

import os
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool, StaticPool

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models.payment import Escrow, Payment, Refund

# Runs against TEST_DATABASE_URL when set (CI uses PostgreSQL), otherwise in-memory SQLite.
TEST_DB = os.environ.get("TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:")


def token(role: str) -> str:
    return jwt.encode({"sub": "u-1", "role": role, "type": "access"}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


ADMIN = {"Authorization": f"Bearer {token('admin')}"}


def at(day: int, hour: int = 12) -> datetime:
    return datetime(2026, 10, day, hour, tzinfo=timezone.utc)


@pytest_asyncio.fixture
async def client():
    # In-memory SQLite must share one connection; real databases must not reuse connections across event loops.
    engine = create_async_engine(TEST_DB, poolclass=StaticPool if ":memory:" in TEST_DB else NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    def payment(pid, day, amount, status="COMPLETED", currency="INR"):
        return Payment(
            id=pid,
            booking_id=f"b-{pid}",
            payer_id="cust-1",
            payee_id=f"prov-{pid}",
            amount_cents=amount,
            currency=currency,
            status=status,
            payment_method="card",
            idempotency_key=pid,
            created_at=at(day),
            updated_at=at(day),
        )

    async with factory() as db:
        db.add_all(
            [
                payment("p1", 1, 10_000),
                payment("p2", 1, 5_000, status="PARTIALLY_REFUNDED"),
                payment("p3", 3, 20_000),
                payment("p4", 3, 9_999, status="FAILED"),  # never collected
                payment("p5", 3, 7_000, status="PENDING"),  # not collected yet
                payment("p6", 2, 50_000, currency="USD"),  # other currency
            ]
        )
        await db.flush()
        db.add_all(
            [
                Refund(id="r1", payment_id="p2", amount_cents=2_000, reason="late", status="PENDING", created_at=at(2)),
                Refund(id="r2", payment_id="p1", amount_cents=1_000, reason="x", status="FAILED", created_at=at(2)),
                Escrow(
                    id="e1",
                    payment_id="p1",
                    booking_id="b-p1",
                    amount_cents=10_000,
                    currency="INR",
                    status="RELEASED",
                    held_at=at(1),
                    released_at=at(2),
                ),
                Escrow(
                    id="e2",
                    payment_id="p3",
                    booking_id="b-p3",
                    amount_cents=20_000,
                    currency="INR",
                    status="HELD",
                    held_at=at(3),
                ),
            ]
        )
        await db.commit()

    async def override_get_db():
        async with factory() as session:
            yield session
            await session.commit()

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_revenue_report_aggregates_by_day(client):
    resp = await client.get(
        "/api/v1/finance/revenue", params={"date_from": "2026-10-01", "date_to": "2026-10-04"}, headers=ADMIN
    )
    assert resp.status_code == 200
    report = resp.json()
    assert report["currency"] == "INR"
    assert report["gross_cents"] == 35_000  # p1 + p2 + p3; FAILED, PENDING and USD excluded
    assert report["refunds_cents"] == 2_000  # failed refunds excluded
    assert report["net_cents"] == 33_000
    assert report["payments"] == 3
    by_day = {p["date"]: p for p in report["series"]}
    assert list(by_day) == ["2026-10-01", "2026-10-02", "2026-10-03", "2026-10-04"]
    assert by_day["2026-10-01"]["gross_cents"] == 15_000
    assert by_day["2026-10-02"] == {
        "date": "2026-10-02",
        "gross_cents": 0,
        "refunds_cents": 2_000,
        "net_cents": -2_000,
        "payments": 0,
    }
    assert by_day["2026-10-04"]["gross_cents"] == 0


@pytest.mark.asyncio
async def test_revenue_report_validates_range(client):
    bad = await client.get(
        "/api/v1/finance/revenue", params={"date_from": "2026-10-05", "date_to": "2026-10-01"}, headers=ADMIN
    )
    assert bad.status_code == 400
    usd = await client.get(
        "/api/v1/finance/revenue",
        params={"date_from": "2026-10-01", "date_to": "2026-10-04", "currency": "usd"},
        headers=ADMIN,
    )
    assert usd.json()["gross_cents"] == 50_000


@pytest.mark.asyncio
async def test_settlements_list_and_filter(client):
    resp = await client.get("/api/v1/finance/settlements", headers=ADMIN)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert [s["id"] for s in body["data"]] == ["e2", "e1"]  # newest first
    assert body["data"][1]["payee_id"] == "prov-p1"

    held = (await client.get("/api/v1/finance/settlements", params={"status": "HELD"}, headers=ADMIN)).json()
    assert [s["id"] for s in held["data"]] == ["e2"]


@pytest.mark.asyncio
async def test_finance_requires_admin(client):
    assert (await client.get("/api/v1/finance/settlements")).status_code in (401, 403)
    user = {"Authorization": f"Bearer {token('user')}"}
    assert (await client.get("/api/v1/finance/settlements", headers=user)).status_code == 403
    assert (await client.get("/api/v1/finance/revenue", headers=user)).status_code == 403
