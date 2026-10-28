"""Booking with loyalty points: the discount comes off the service's price, and completed bookings say whose they are."""

import pytest

from app.core import payments
from app.core.points import get_points_wallet
from app.main import app
from app.models.booking import Booking
from tests import test_availability
from tests.test_availability import MON, book

# The API client with test_availability's opening hours and clock.
client = test_availability.client


class FakeWallet:
    def __init__(self, discount: int):
        self.discount = discount
        self.redeemed: list = []
        self.released: list = []

    async def redeem(self, customer_id, booking_id, price_cents):
        self.redeemed.append((customer_id, booking_id, price_cents))
        return self.discount

    async def release(self, booking_id):
        self.released.append(booking_id)


@pytest.mark.asyncio
async def test_points_come_off_the_price_and_are_shown_on_the_booking(client):
    wallet = FakeWallet(9980)
    app.dependency_overrides[get_points_wallet] = lambda: wallet
    resp = await book(client, MON, "10:00", use_points=True)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert (body["total_amount"], body["list_price"], body["points_discount"]) == (49900 - 9980, 49900, 9980)
    [(customer, booking_id, price)] = wallet.redeemed
    assert (customer, booking_id, price) == ("c5", body["id"], 49900)  # spent on this very booking


@pytest.mark.asyncio
async def test_without_asking_no_points_are_spent(client):
    wallet = FakeWallet(5000)
    app.dependency_overrides[get_points_wallet] = lambda: wallet
    resp = await book(client, MON, "11:00")
    assert resp.json()["total_amount"] == 49900 and resp.json()["points_discount"] == 0
    assert wallet.redeemed == []


@pytest.mark.asyncio
async def test_no_points_or_no_answer_books_at_the_normal_price(client):
    app.dependency_overrides[get_points_wallet] = lambda: FakeWallet(0)
    resp = await book(client, MON, "12:00", use_points=True)
    assert resp.status_code == 201
    assert (resp.json()["total_amount"], resp.json()["points_discount"]) == (49900, 0)


def test_a_completed_booking_says_whose_points_it_earns():
    booking = Booking(id="b", customer_id="c5", shop_id="shop-1", total_amount=1000)
    payload = payments.payload_for(payments.COMPLETED, booking, payments_now())
    assert (payload["customer_id"], payload["total_amount"], payload["shop_id"]) == ("c5", 1000, "shop-1")


def payments_now():
    from datetime import datetime, timezone

    return datetime(2030, 11, 4, tzinfo=timezone.utc)
