"""A double tap or a network retry that sends the same booking request several times at once makes one booking.

The races need real concurrent transactions, so these run only when TEST_DATABASE_URL points at PostgreSQL
(as in CI); the retry behaviour itself is covered on SQLite in test_shop_bookings_api.
"""

import asyncio
import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.main import app
from app.models.booking import Booking
from app.services.booking_service import booking_service
from tests.test_shop_bookings_api import PRICED, SENT, SESSIONS, auth, close_service, open_service

TEST_DB = os.environ.get("TEST_DATABASE_URL", "")
needs_postgres = pytest.mark.skipif(not TEST_DB.startswith("postgresql"), reason="races need PostgreSQL")


@pytest_asyncio.fixture
async def pg_client():
    """The app on TEST_DATABASE_URL, each request on its own connection, as in production."""
    engine = await open_service()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    await close_service(engine)


BODY = {"service_id": "svc-a", "scheduled_at": "2031-01-10T05:00:00Z"}


async def bookings_by(customer_id):
    async with SESSIONS["factory"]() as db:
        return (await db.execute(select(Booking).where(Booking.customer_id == customer_id))).scalars().all()


def tap(client, body, key):
    return client.post("/api/v1/bookings", json=body, headers={**auth("racer"), "Idempotency-Key": key})


@needs_postgres
@pytest.mark.asyncio
async def test_ten_copies_of_one_request_at_once_make_one_booking_and_use_the_coupon_once(pg_client):
    body = {**BODY, "coupon_code": "WELCOME10"}
    replies = await asyncio.gather(*[tap(pg_client, body, "tap-1") for _ in range(10)])

    assert sorted(r.status_code for r in replies) == [200] * 9 + [201]
    assert len({r.json()["id"] for r in replies}) == 1
    assert {r.json()["total_amount"] for r in replies} == {44910}
    assert PRICED == [("racer", 49900, "WELCOME10")]
    assert [event for event, _, _ in SENT] == ["booking.created"]
    assert len(await bookings_by("racer")) == 1


@needs_postgres
@pytest.mark.asyncio
async def test_the_unique_constraint_alone_lets_exactly_one_copy_win(pg_client, monkeypatch):
    # Without the lock every copy gets as far as the insert; the constraint decides, the rest are told the winner.
    async def no_lock(db, customer_id, key):
        return None

    monkeypatch.setattr(booking_service, "hold_idempotency_key", no_lock)
    replies = await asyncio.gather(*[tap(pg_client, BODY, "tap-2") for _ in range(10)])

    assert sorted(r.status_code for r in replies) == [200] * 9 + [201]
    assert len({r.json()["id"] for r in replies}) == 1
    assert len(await bookings_by("racer")) == 1
