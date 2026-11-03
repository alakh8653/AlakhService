"""Removing or rejecting a shop takes its bookings with it, or does not happen at all. Pausing one touches nothing."""

import pytest
from fastapi import HTTPException

from app.dependencies import get_shop_booking_canceller
from app.main import app
from tests import test_reviews_api
from tests.test_reviews_api import ADMIN, auth, make_shop

client = test_reviews_api.client
OWNER = auth("owner-1")


class FakeCanceller:
    def __init__(self, error=None):
        self.calls = []
        self.because = []
        self.error = error

    async def __call__(self, shop_id, because="removed"):
        self.calls.append(shop_id)
        self.because.append(because)
        if self.error:
            raise self.error


def use(canceller):
    app.dependency_overrides[get_shop_booking_canceller] = lambda: canceller
    return canceller


@pytest.mark.asyncio
async def test_removing_a_shop_cancels_its_bookings_and_hides_it(client):
    shop_id = await make_shop(client)
    canceller = use(FakeCanceller())
    assert (await client.delete(f"/api/v1/shops/{shop_id}", headers=OWNER)).status_code == 204
    # Before closing it, and again afterwards for anything booked meanwhile.
    assert canceller.calls == [shop_id, shop_id]
    assert (await client.get(f"/api/v1/shops/{shop_id}")).status_code == 404
    assert (await client.get(f"/api/v1/shops/{shop_id}/hours")).json()["accepting_bookings"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status, detail",
    [(409, "1 booking(s) are being served: finish them first"), (503, "Booking service unavailable")],
)
async def test_the_shop_stays_when_its_bookings_could_not_be_cancelled(client, status, detail):
    shop_id = await make_shop(client)
    canceller = use(FakeCanceller(HTTPException(status_code=status, detail=detail)))
    resp = await client.delete(f"/api/v1/shops/{shop_id}", headers=OWNER)
    assert (resp.status_code, resp.json()["detail"]) == (status, detail)
    assert canceller.calls == [shop_id]
    assert (await client.get(f"/api/v1/shops/{shop_id}")).status_code == 200


@pytest.mark.asyncio
async def test_a_failure_of_the_second_pass_does_not_undo_the_removal(client):
    shop_id = await make_shop(client)

    class FailsSecondTime(FakeCanceller):
        async def __call__(self, shop_id, because="removed"):
            self.calls.append(shop_id)
            if len(self.calls) == 2:
                raise HTTPException(status_code=503, detail="Booking service unavailable")

    use(FailsSecondTime())
    assert (await client.delete(f"/api/v1/shops/{shop_id}", headers=OWNER)).status_code == 204
    assert (await client.get(f"/api/v1/shops/{shop_id}")).status_code == 404


@pytest.mark.asyncio
async def test_only_the_owner_can_remove_it_and_a_stranger_cancels_nothing(client):
    shop_id = await make_shop(client)
    canceller = use(FakeCanceller())
    assert (await client.delete(f"/api/v1/shops/{shop_id}", headers=auth("someone-else"))).status_code == 403
    assert canceller.calls == []


@pytest.mark.asyncio
async def test_pausing_a_shop_leaves_its_bookings_alone(client):
    shop_id = await make_shop(client)
    canceller = use(FakeCanceller())
    assert (await client.put(f"/api/v1/shops/{shop_id}", json={"is_active": False}, headers=OWNER)).status_code == 200
    assert canceller.calls == []


REASON = {"reason": "The PAN card is forged"}


@pytest.mark.asyncio
async def test_rejecting_a_shop_cancels_its_bookings_and_hides_it(client):
    shop_id = await make_shop(client)
    canceller = use(FakeCanceller())
    resp = await client.post(f"/api/v1/admin/shops/{shop_id}/reject", json=REASON, headers=ADMIN)
    assert (resp.status_code, resp.json()["verification_status"]) == (200, "REJECTED")
    # Before rejecting it, and again afterwards for anything booked meanwhile.
    assert canceller.calls == [shop_id, shop_id]
    assert canceller.because == ["rejected", "rejected"]
    assert (await client.get(f"/api/v1/shops/{shop_id}")).status_code == 404
    assert (await client.get(f"/api/v1/shops/{shop_id}/hours")).json()["accepting_bookings"] is False


@pytest.mark.asyncio
async def test_the_shop_stays_as_it_was_when_booking_service_is_down_during_a_rejection(client):
    shop_id = await make_shop(client)
    canceller = use(FakeCanceller(HTTPException(status_code=503, detail="Booking service unavailable")))
    resp = await client.post(f"/api/v1/admin/shops/{shop_id}/reject", json=REASON, headers=ADMIN)
    assert (resp.status_code, resp.json()["detail"]) == (503, "Booking service unavailable")
    assert canceller.calls == [shop_id]
    assert (await client.get(f"/api/v1/shops/{shop_id}")).json()["verification_status"] != "REJECTED"


@pytest.mark.asyncio
async def test_a_failure_of_the_second_pass_does_not_undo_the_rejection(client):
    shop_id = await make_shop(client)

    class FailsSecondTime(FakeCanceller):
        async def __call__(self, shop_id, because="removed"):
            self.calls.append(shop_id)
            if len(self.calls) == 2:
                raise HTTPException(status_code=503, detail="Booking service unavailable")

    use(FailsSecondTime())
    resp = await client.post(f"/api/v1/admin/shops/{shop_id}/reject", json=REASON, headers=ADMIN)
    assert (resp.status_code, resp.json()["verification_status"]) == (200, "REJECTED")


@pytest.mark.asyncio
async def test_only_admins_can_reject_and_anyone_else_cancels_nothing(client):
    shop_id = await make_shop(client)
    canceller = use(FakeCanceller())
    resp = await client.post(f"/api/v1/admin/shops/{shop_id}/reject", json=REASON, headers=OWNER)
    assert resp.status_code == 403
    assert canceller.calls == []
