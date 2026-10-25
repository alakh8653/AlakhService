"""payment_service hears about completed, cancelled and disputed bookings; reminders and expiry."""

import json
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.config import settings
from app.core import payments, worker
from app.core.payments import get_payment_client, get_session_factory
from app.main import app
from app.models.booking import Booking, PaymentOutbox
from tests.test_shop_bookings_api import OWNERS, SENT, SESSIONS, auth, close_service, open_service

KEY = "k" * 40
INTERNAL = {"X-Internal-Key": KEY}
NOW = datetime.now(timezone.utc).replace(microsecond=0)


class FakePayments:
    """Stands in for payment_service's internal routes; set `down` to make it fail."""

    def __init__(self):
        self.sent = []
        self.down = False

    @property
    def configured(self):
        return True

    async def send(self, booking_id, kind, payload):
        if self.down:
            return "unreachable: connection refused"
        self.sent.append((booking_id, kind, payload))
        return None


PAY = FakePayments()


@pytest_asyncio.fixture
async def http(monkeypatch):
    engine = await open_service()
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", KEY)
    PAY.sent.clear()
    PAY.down = False
    app.dependency_overrides[get_payment_client] = lambda: PAY
    app.dependency_overrides[get_session_factory] = lambda: SESSIONS["factory"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    await close_service(engine)


async def outbox():
    async with SESSIONS["factory"]() as db:
        return list((await db.execute(select(PaymentOutbox).order_by(PaymentOutbox.created_at))).scalars().all())


async def stored(booking_id):
    async with SESSIONS["factory"]() as db:
        return await db.get(Booking, booking_id)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "who, expected", [(auth("c3"), "customer"), (auth("owner-1"), "shop"), (auth("x", "admin"), "admin")]
)
async def test_a_cancel_asks_payment_service_for_the_refund(http, who, expected):
    resp = await http.post("/api/v1/bookings/bk-4/cancel", json={"reason": "Plans changed"}, headers=who)
    assert resp.status_code == 200
    [(booking_id, kind, payload)] = PAY.sent
    assert (booking_id, kind, payload["cancelled_by"]) == ("bk-4", "cancelled", expected)
    assert payload["scheduled_at"].startswith("2026-10-03T10:00:00")
    assert payload["cancelled_at"]
    [row] = await outbox()
    assert row.delivered_at is not None


@pytest.mark.asyncio
async def test_the_cancel_works_while_payment_service_is_down_and_is_retried(http):
    PAY.down = True
    resp = await http.post("/api/v1/bookings/bk-4/cancel", json={"reason": "x"}, headers=auth("c3"))
    assert (resp.status_code, resp.json()["status"]) == (200, "CANCELLED")
    [row] = await outbox()
    assert (row.delivered_at, row.attempts) == (None, 1)
    assert "unreachable" in row.last_error

    # Not due yet: nothing is retried.
    async with SESSIONS["factory"]() as db:
        assert await payments.deliver_due(db, PAY, datetime.now(timezone.utc)) == []
    PAY.down = False
    async with SESSIONS["factory"]() as db:
        tried = await payments.deliver_due(db, PAY, datetime.now(timezone.utc) + timedelta(minutes=5))
        await db.commit()
    assert len(tried) == 1
    assert [k for _, k, _ in PAY.sent] == ["cancelled"]
    [row] = await outbox()
    assert (row.delivered_at is not None, row.attempts) == (True, 2)


@pytest.mark.asyncio
async def test_backoff_grows_and_is_capped():
    row = PaymentOutbox(booking_id="b", kind="cancelled", payload="{}", attempts=0, next_attempt_at=NOW)

    class Down:
        configured = True

        async def send(self, *a):
            return "500: boom"

    delays = []
    for _ in range(10):
        await payments._attempt(None, row, Down(), NOW)
        delays.append(row.next_attempt_at - NOW)
    assert delays[:3] == [timedelta(seconds=30), timedelta(seconds=60), timedelta(seconds=120)]
    assert delays[-1] == timedelta(hours=1)


@pytest.mark.asyncio
async def test_completing_a_booking_tells_payment_service_once(http):
    owner = auth("owner-1")
    for status in ("CONFIRMED", "IN_PROGRESS", "COMPLETED"):
        assert (
            await http.put("/api/v1/bookings/bk-4/status", json={"status": status}, headers=owner)
        ).status_code == 200
    assert PAY.sent == [("bk-4", "completed", PAY.sent[0][2])]
    assert PAY.sent[0][2]["shop_id"] == "shop-1"
    assert PAY.sent[0][2]["total_amount"] == 2000
    # Disputing it puts the shop's earning on hold.
    assert (
        await http.put("/api/v1/bookings/bk-4/status", json={"status": "DISPUTED"}, headers=auth("c3"))
    ).status_code == 200
    assert [k for _, k, _ in PAY.sent] == ["completed", "disputed"]


@pytest.mark.asyncio
async def test_payment_status_is_set_by_payment_service_and_shown(http):
    url = "/internal/bookings/bk-4/payment-status"
    assert (await http.post(url, json={"payment_status": "PAID"})).status_code == 401
    assert (
        await http.post(url, json={"payment_status": "PAID"}, headers={"X-Internal-Key": "nope"})
    ).status_code == 401
    assert (await http.post(url, json={"payment_status": "RICH"}, headers=INTERNAL)).status_code == 422
    assert (
        await http.post("/internal/bookings/nope/payment-status", json={"payment_status": "PAID"}, headers=INTERNAL)
    ).status_code == 404
    assert (await http.get("/api/v1/bookings/bk-4", headers=auth("c3"))).json()["payment_status"] == "UNPAID"
    done = await http.post(url, json={"payment_status": "PAID"}, headers=INTERNAL)
    assert done.json() == {"booking_id": "bk-4", "payment_status": "PAID"}
    assert (await http.get("/api/v1/bookings/bk-4", headers=auth("c3"))).json()["payment_status"] == "PAID"
    shop_view = (await http.get("/api/v1/bookings/shop/shop-1", headers=auth("owner-1"))).json()
    assert {b["id"]: b["payment_status"] for b in shop_view["items"]}["bk-4"] == "PAID"


@pytest.mark.asyncio
async def test_resolving_a_dispute_refunded_or_completed(http):
    assert (
        await http.put("/api/v1/bookings/bk-1/status", json={"status": "DISPUTED"}, headers=auth("c1"))
    ).status_code == 200
    url = "/internal/bookings/bk-1/resolve-dispute"
    SENT.clear()
    refunded = await http.post(url, json={"outcome": "REFUNDED"}, headers=INTERNAL)
    assert refunded.json() == {"booking_id": "bk-1", "status": "REFUNDED", "changed": True}
    assert [(e, r) for e, r, _ in SENT] == [("booking.refunded", [("c1", "customer"), ("owner-1", "shop")])]
    again = await http.post(url, json={"outcome": "REFUNDED"}, headers=INTERNAL)
    assert again.json()["changed"] is False
    assert len(SENT) == 1
    assert (await http.post(url, json={"outcome": "COMPLETED"}, headers=INTERNAL)).status_code == 409
    assert (await http.post(url, json={"outcome": "LOST"}, headers=INTERNAL)).status_code == 422

    # In the shop's favour: completed again, and payment_service is told (it ignores a repeat).
    assert (
        await http.put("/api/v1/bookings/bk-2/status", json={"status": "DISPUTED"}, headers=auth("c2"))
    ).status_code == 200
    PAY.sent.clear()
    done = await http.post("/internal/bookings/bk-2/resolve-dispute", json={"outcome": "COMPLETED"}, headers=INTERNAL)
    assert done.json()["status"] == "COMPLETED"
    assert [(b, k) for b, k, _ in PAY.sent] == [("bk-2", "completed")]
    assert (await stored("bk-2")).status == "COMPLETED"


def new_booking(n, status, scheduled_at, created_at=None, customer="cust"):
    created = created_at or NOW - timedelta(hours=1)
    return Booking(
        id=f"w-{n}",
        booking_number=f"BKW-{n}",
        customer_id=customer,
        service_id="svc-a",
        shop_id="shop-1",
        status=status,
        scheduled_at=scheduled_at,
        duration_minutes=30,
        total_amount=1000,
        created_at=created,
        updated_at=created,
    )


class Notes:
    def __init__(self):
        self.sent = []

    async def send(self, event, recipients, data):
        self.sent.append((event, data["booking_id"], tuple(r["role"] for r in recipients), data))


async def fake_owner(shop_id):
    return OWNERS.get(shop_id)


@pytest.mark.asyncio
async def test_reminders_go_out_24h_and_1h_before_each_once(http):
    async with SESSIONS["factory"]() as db:
        db.add_all(
            [
                new_booking(1, "CONFIRMED", NOW + timedelta(minutes=30)),
                new_booking(2, "ASSIGNED", NOW + timedelta(hours=5)),
                new_booking(3, "CONFIRMED", NOW + timedelta(hours=30)),  # too far
                new_booking(4, "CANCELLED", NOW + timedelta(minutes=20)),  # not happening
                new_booking(5, "IN_PROGRESS", NOW + timedelta(minutes=10)),  # already started
                new_booking(6, "CONFIRMED", NOW - timedelta(minutes=10)),  # in the past
            ]
        )
        await db.commit()
    notes = Notes()
    first = await worker.run_once(SESSIONS["factory"], notes, fake_owner, PAY, now=NOW)
    assert first["reminders"] == 2
    got = sorted((b, d["reminder"]) for e, b, _, d in notes.sent if e == "booking.reminder")
    assert got == [("w-1", "1h"), ("w-2", "24h")]
    assert all(roles == ("customer", "shop") for e, _, roles, _ in notes.sent)

    notes.sent.clear()
    assert (await worker.run_once(SESSIONS["factory"], notes, fake_owner, PAY, now=NOW))["reminders"] == 0
    # Four and a half hours later w-2 is half an hour away: its one-hour reminder.
    later = NOW + timedelta(hours=4, minutes=30)
    await worker.run_once(SESSIONS["factory"], notes, fake_owner, PAY, now=later)
    assert [(b, d["reminder"]) for e, b, _, d in notes.sent if e == "booking.reminder"] == [("w-2", "1h")]
    # w-1 got only the one-hour reminder, and never a "tomorrow" afterwards.
    w1 = await stored("w-1")
    assert w1.reminder_1h_sent_at is not None and w1.reminder_24h_sent_at is not None


@pytest.mark.asyncio
async def test_unconfirmed_bookings_expire_and_are_refunded(http):
    async with SESSIONS["factory"]() as db:
        db.add_all(
            [
                new_booking(10, "PENDING", NOW + timedelta(days=2), created_at=NOW - timedelta(hours=13)),
                new_booking(11, "PENDING", NOW - timedelta(minutes=5)),  # its time has come
                new_booking(12, "PENDING", NOW + timedelta(days=1)),  # the shop still has time
                new_booking(13, "CONFIRMED", NOW + timedelta(days=2), created_at=NOW - timedelta(hours=20)),
            ]
        )
        await db.commit()
    notes = Notes()
    out = await worker.run_once(SESSIONS["factory"], notes, fake_owner, PAY, now=NOW)
    assert out["expired"] >= 2
    for bid in ("w-10", "w-11"):
        b = await stored(bid)
        assert (b.status, b.cancellation_reason) == ("CANCELLED", "Shop did not confirm")
    assert (await stored("w-12")).status == "PENDING"
    assert (await stored("w-13")).status == "CONFIRMED"
    refunds = {b: p for b, k, p in PAY.sent if k == "cancelled"}
    assert refunds["w-10"]["cancelled_by"] == "shop"
    assert "w-11" in refunds
    expired = {b: (roles, d) for e, b, roles, d in notes.sent if e == "booking.expired"}
    assert expired["w-10"][0] == ("customer", "shop")
    assert expired["w-10"][1]["reason"] == "Shop did not confirm"
    # A second pass finds nothing more to do.
    notes.sent.clear()
    again = await worker.run_once(SESSIONS["factory"], notes, fake_owner, PAY, now=NOW)
    assert again["expired"] == 0 and not notes.sent


@pytest.mark.asyncio
async def test_payment_messages_are_queued_once_per_kind(http):
    async with SESSIONS["factory"]() as db:
        b = await db.get(Booking, "bk-4")
        first = await payments.enqueue(db, b, payments.CANCELLED, "customer")
        second = await payments.enqueue(db, b, payments.CANCELLED, "shop")
        await db.commit()
    assert first.id == second.id
    assert json.loads(first.payload)["cancelled_by"] == "customer"


def test_the_worker_is_off_under_tests():
    assert settings.REMINDERS_ENABLED is False
