"""Shop-scoped booking list and summary, with ownership enforced."""
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
from app.dependencies import get_shop_owner_lookup
from app.main import app
from app.models.booking import Booking

TEST_DB = os.environ.get("TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
OWNERS = {"shop-1": "owner-1", "shop-2": "owner-2"}


def auth(sub: str, role: str = "user") -> dict:
    token = jwt.encode({"sub": sub, "role": role, "type": "access"}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {"Authorization": f"Bearer {token}"}


def booking(n, shop, status, day, amount=1000, service="svc-a", customer="c1", provider=None):
    at = datetime(2026, 10, day, 10, tzinfo=timezone.utc)
    return Booking(
        id=f"bk-{n}", booking_number=f"BK-{n}", customer_id=customer, provider_id=provider, service_id=service,
        shop_id=shop, status=status, scheduled_at=at, duration_minutes=60, total_amount=amount,
        created_at=at, updated_at=at,
    )


@pytest_asyncio.fixture
async def client():
    engine = create_async_engine(TEST_DB, poolclass=StaticPool if ":memory:" in TEST_DB else NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        db.add_all([
            booking(1, "shop-1", "COMPLETED", 1, 5000, "svc-a", "c1", "staff-1"),
            booking(2, "shop-1", "COMPLETED", 1, 3000, "svc-b", "c2"),
            booking(3, "shop-1", "CANCELLED", 2, 4000, "svc-a", "c1"),
            booking(4, "shop-1", "PENDING", 3, 2000, "svc-a", "c3", "staff-1"),
            booking(5, "shop-1", "COMPLETED", 20, 9000, "svc-a", "c1"),   # outside the summary range
            booking(6, "shop-2", "COMPLETED", 1, 7000, "svc-z", "c9"),    # another shop
        ])
        await db.commit()

    async def override_get_db():
        async with factory() as session:
            yield session
            await session.commit()

    async def fake_owner(shop_id):
        return OWNERS.get(shop_id)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_shop_owner_lookup] = lambda: fake_owner
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_only_the_owner_or_an_admin_sees_shop_bookings(client):
    assert (await client.get("/api/v1/bookings/shop/shop-1")).status_code in (401, 403)
    assert (await client.get("/api/v1/bookings/shop/shop-1", headers=auth("owner-2"))).status_code == 403
    assert (await client.get("/api/v1/bookings/shop/nope", headers=auth("owner-1"))).status_code == 404
    assert (await client.get("/api/v1/bookings/shop/shop-1", headers=auth("someone", "admin"))).status_code == 200


@pytest.mark.asyncio
async def test_list_filters_by_status_provider_and_date(client):
    owner = auth("owner-1")
    everything = (await client.get("/api/v1/bookings/shop/shop-1", headers=owner)).json()
    assert everything["total"] == 5
    assert everything["items"][0]["id"] == "bk-5"  # latest scheduled first
    assert all(b["shop_id"] == "shop-1" for b in everything["items"])

    completed = (await client.get("/api/v1/bookings/shop/shop-1", params={"status": "COMPLETED"}, headers=owner)).json()
    assert {b["id"] for b in completed["items"]} == {"bk-1", "bk-2", "bk-5"}

    staff = (await client.get("/api/v1/bookings/shop/shop-1", params={"provider_id": "staff-1"}, headers=owner)).json()
    assert {b["id"] for b in staff["items"]} == {"bk-1", "bk-4"}

    window = (
        await client.get("/api/v1/bookings/shop/shop-1", params={"date_from": "2026-10-02", "date_to": "2026-10-03"}, headers=owner)
    ).json()
    assert {b["id"] for b in window["items"]} == {"bk-3", "bk-4"}


@pytest.mark.asyncio
async def test_summary(client):
    resp = await client.get(
        "/api/v1/bookings/shop/shop-1/summary", params={"date_from": "2026-10-01", "date_to": "2026-10-03"}, headers=auth("owner-1")
    )
    assert resp.status_code == 200
    s = resp.json()
    assert s["total_bookings"] == 4
    assert s["total_revenue"] == 8000              # completed only: 5000 + 3000
    assert s["unique_customers"] == 3
    assert s["by_status"] == {"COMPLETED": 2, "CANCELLED": 1, "PENDING": 1}
    assert s["by_day"] == [
        {"day": "2026-10-01", "revenue": 8000, "bookings": 2},
        {"day": "2026-10-02", "revenue": 0, "bookings": 1},
        {"day": "2026-10-03", "revenue": 0, "bookings": 1},
    ]
    assert s["top_services"][0] == {"service_id": "svc-a", "bookings": 3, "revenue": 5000}

    bad = await client.get(
        "/api/v1/bookings/shop/shop-1/summary", params={"date_from": "2026-10-05", "date_to": "2026-10-01"}, headers=auth("owner-1")
    )
    assert bad.status_code == 400
