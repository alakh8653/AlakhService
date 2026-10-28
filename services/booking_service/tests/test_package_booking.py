"""Booking a visit with a prepaid package: it costs nothing more, or is refused if the package cannot be used."""

import pytest

from app.core.packages import PackageUnusable, get_package_wallet
from app.main import app
from tests import test_availability
from tests.test_availability import MON, book

# The API client with test_availability's opening hours and clock.
client = test_availability.client


class FakePackages:
    def __init__(self, refuse: PackageUnusable | None = None):
        self.refuse = refuse
        self.used: list = []

    async def redeem(self, customer_id, purchase_id, service_id, booking_id):
        if self.refuse:
            raise self.refuse
        self.used.append((customer_id, purchase_id, service_id, booking_id))
        return 24000

    async def release(self, booking_id):
        pass


@pytest.mark.asyncio
async def test_a_package_visit_costs_nothing_more(client):
    packages = FakePackages()
    app.dependency_overrides[get_package_wallet] = lambda: packages
    resp = await book(client, MON, "10:00", package_purchase_id="pp-1")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert (body["total_amount"], body["list_price"], body["package_purchase_id"]) == (0, 49900, "pp-1")
    assert packages.used == [("c5", "pp-1", "svc-a", body["id"])]


@pytest.mark.asyncio
async def test_a_package_that_cannot_be_used_refuses_the_booking(client):
    app.dependency_overrides[get_package_wallet] = lambda: FakePackages(
        PackageUnusable(409, "This package has expired")
    )
    resp = await book(client, MON, "10:00", package_purchase_id="pp-old")
    assert (resp.status_code, resp.json()["detail"]) == (409, "This package has expired")


@pytest.mark.asyncio
async def test_a_package_is_not_combined_with_a_coupon_or_points(client):
    packages = FakePackages()
    app.dependency_overrides[get_package_wallet] = lambda: packages
    assert (await book(client, MON, "10:00", package_purchase_id="pp-1", coupon_code="WELCOME10")).status_code == 422
    assert (await book(client, MON, "10:00", package_purchase_id="pp-1", use_points=True)).status_code == 422
    assert packages.used == []
