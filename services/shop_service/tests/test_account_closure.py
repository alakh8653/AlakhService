"""Deleting an owner's account closes their business and erases their ID and bank details, or changes nothing."""

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.core.reporting import get_reporter
from app.core.storage import LocalDocumentStorage, get_storage
from app.database import get_db
from app.dependencies import get_shop_booking_canceller
from app.main import app
from app.models.shop import Shop, ShopDocument, ShopPayoutDetails, ShopWorkPhoto
from app.routers.account_closure import get_payment_peer
from tests import test_reviews_api
from tests.test_kyc_api import FakeReporter
from tests.test_reviews_api import ADMIN, auth, make_shop
from tests.test_shop_removal import FakeCanceller
from tests.test_work_photos import photo, upload

client = test_reviews_api.client
OWNER = auth("owner-1")
URL = "/api/v1/shops/mine"


class FakePayments:
    def __init__(self, owed=0, error=None):
        self.owed = owed
        self.error = error
        self.forgotten = []

    async def owed_cents(self, shop_id):
        if self.error:
            raise self.error
        return self.owed

    async def forget(self, shop_id):
        self.forgotten.append(shop_id)


@pytest.fixture(autouse=True)
def setup(tmp_path):
    state = {"root": tmp_path, "canceller": FakeCanceller(), "payments": FakePayments(), "reporter": FakeReporter()}
    app.dependency_overrides[get_storage] = lambda: LocalDocumentStorage(str(tmp_path))
    app.dependency_overrides[get_shop_booking_canceller] = lambda: state["canceller"]
    app.dependency_overrides[get_payment_peer] = lambda: state["payments"]
    app.dependency_overrides[get_reporter] = lambda: state["reporter"]
    return state


async def full_shop(client):  # noqa: F811
    shop_id = await make_shop(client)
    url = f"/api/v1/shops/{shop_id}"
    # Set by an admin: an approved shop's owner cannot change its verified legal name alone.
    details = {"legal_name": "Ravi Kumar", "phone": "+919812345678", "description": "About"}
    assert (await client.put(url, json=details, headers=ADMIN)).status_code == 200
    await client.post(
        f"{url}/documents/upload",
        params={"type": "PAN"},
        content=b"%PDF-1.4 my pan card",
        headers={**OWNER, "Content-Type": "application/pdf"},
    )
    await upload(client, shop_id, photo())
    await client.put(
        f"{url}/payout-details", json={"method": "UPI", "account_name": "Ravi", "upi_id": "ravi@upi"}, headers=OWNER
    )
    return shop_id


async def stored(shop_id):
    gen = app.dependency_overrides[get_db]()
    db = await gen.__anext__()
    shop = await db.get(Shop, shop_id)
    counts = {
        m.__name__: len((await db.execute(select(m).where(m.shop_id == shop_id))).scalars().all())
        for m in (ShopDocument, ShopWorkPhoto, ShopPayoutDetails)
    }
    values = (shop.is_active, shop.phone, shop.description, shop.legal_name)
    await gen.aclose()
    return values, counts


def files(root):
    return [p for p in root.rglob("*") if p.is_file()]


@pytest.mark.asyncio
async def test_the_shop_closes_and_id_bank_and_photos_are_erased_but_invoice_details_stay(client, setup):
    shop_id = await full_shop(client)
    assert (await stored(shop_id))[1] == {"ShopDocument": 1, "ShopWorkPhoto": 1, "ShopPayoutDetails": 1}
    assert len(files(setup["root"])) == 2

    assert (await client.delete(URL, headers=OWNER)).status_code == 204

    values, counts = await stored(shop_id)
    assert values == (False, None, None, "Ravi Kumar")
    assert counts == {"ShopDocument": 0, "ShopWorkPhoto": 0, "ShopPayoutDetails": 0}
    assert files(setup["root"]) == []
    # Bookings were cancelled first, and again for any made meanwhile.
    assert setup["canceller"].calls == [shop_id, shop_id]
    assert setup["reporter"].listings[-1] == (shop_id, False)
    assert setup["payments"].forgotten == [shop_id]
    assert (await client.get(f"/api/v1/shops/{shop_id}")).status_code == 404


@pytest.mark.asyncio
async def test_money_still_owed_stops_it_and_changes_nothing(client, setup):
    shop_id = await full_shop(client)
    setup["payments"].owed = 150000
    resp = await client.delete(URL, headers=OWNER)
    assert resp.status_code == 409 and "still owed ₹1,500.00" in resp.json()["detail"]
    assert (await stored(shop_id))[1]["ShopPayoutDetails"] == 1
    assert setup["canceller"].calls == []
    assert len(files(setup["root"])) == 2


@pytest.mark.asyncio
async def test_money_the_shop_owes_us_does_not_stop_it(client, setup):
    await full_shop(client)
    setup["payments"].owed = -500
    assert (await client.delete(URL, headers=OWNER)).status_code == 204


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "where, status",
    [("payments", 503), ("canceller", 409), ("canceller", 503)],
)
async def test_a_job_being_served_or_an_outage_changes_nothing(client, setup, where, status):
    shop_id = await full_shop(client)
    error = HTTPException(status_code=status, detail="Not now")
    if where == "payments":
        setup["payments"].error = error
    else:
        setup["canceller"].error = error
    assert (await client.delete(URL, headers=OWNER)).status_code == status
    values, counts = await stored(shop_id)
    assert values[0] is True
    assert counts["ShopDocument"] == 1
    assert len(files(setup["root"])) == 2


@pytest.mark.asyncio
async def test_someone_without_a_shop_is_fine_and_repeating_it_is_safe(client, setup):
    assert (await client.delete(URL, headers=auth("just-a-customer"))).status_code == 204
    shop_id = await full_shop(client)
    assert (await client.delete(URL, headers=auth("someone-else"))).status_code == 204
    assert (await stored(shop_id))[0][0] is True
    assert (await client.delete(URL, headers=OWNER)).status_code == 204
    assert (await client.delete(URL, headers=OWNER)).status_code == 204


@pytest.mark.asyncio
async def test_it_needs_a_sign_in(client):
    assert (await client.delete(URL)).status_code in (401, 403)
