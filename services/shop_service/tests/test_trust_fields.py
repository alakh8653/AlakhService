"""Customer trust: the free-fix period a shop promises (guarantee_days) and when it was verified."""

import pytest

from tests.test_kyc_api import client, new_shop, reporter  # noqa: F401
from tests.test_staff_api import ADMIN, OTHER, OWNER


@pytest.mark.asyncio
async def test_guarantee_days_default_to_a_week_and_only_the_owner_sets_them_within_0_to_90(client):  # noqa: F811
    shop = await new_shop(client)
    assert shop["guarantee_days"] == 7
    url = f"/api/v1/shops/{shop['id']}"
    assert (await client.put(url, json={"guarantee_days": 30}, headers=OTHER)).status_code == 403
    for bad in (-1, 91, None):
        assert (await client.put(url, json={"guarantee_days": bad}, headers=OWNER)).status_code == 422
    updated = await client.put(url, json={"guarantee_days": 30}, headers=OWNER)
    assert updated.status_code == 200 and updated.json()["guarantee_days"] == 30
    assert (await client.put(url, json={"guarantee_days": 0}, headers=OWNER)).json()["guarantee_days"] == 0
    # booking_service reads it with the opening hours.
    hours = await client.get(f"{url}/hours")
    assert hours.json()["guarantee_days"] == 0


@pytest.mark.asyncio
async def test_verified_at_is_public_set_on_approval_and_cleared_on_rejection(client):  # noqa: F811
    shop = await new_shop(client)
    assert (shop["is_verified"], shop["verified_at"]) == (False, None)
    await client.put(f"/api/v1/shops/{shop['id']}", json={"guarantee_days": 14}, headers=OWNER)
    approved = await client.post(f"/api/v1/admin/shops/{shop['id']}/approve", headers=ADMIN)
    assert approved.status_code == 200
    public = (await client.get(f"/api/v1/shops/{shop['id']}")).json()
    assert public["is_verified"] is True and public["verified_at"] is not None
    assert public["guarantee_days"] == 14
    listed = (await client.get("/api/v1/shops")).json()
    assert listed[0]["verified_at"] == public["verified_at"]

    rejected = await client.post(
        f"/api/v1/admin/shops/{shop['id']}/reject", json={"reason": "Forged licence"}, headers=ADMIN
    )
    assert rejected.status_code == 200
    assert (rejected.json()["is_verified"], rejected.json()["verified_at"]) == (False, None)
