"""A shop's own customers: who they are by display name, how often they came, and nothing to contact them by."""

import pytest

from tests.test_shop_bookings_api import auth, client  # noqa: F401  (client is a fixture)

URL = "/api/v1/bookings/shop/shop-1/customers"


@pytest.mark.asyncio
async def test_completed_visits_are_counted_and_contact_details_are_absent(client):  # noqa: F811
    resp = await client.get(URL, headers=auth("owner-1"))
    assert resp.status_code == 200
    rows = resp.json()
    assert rows, "the seeded shop has completed bookings"
    for row in rows:
        assert set(row) == {"name", "visits", "spent", "last_visit"}
        assert row["visits"] >= 1
    # Most recent first.
    assert [r["last_visit"] for r in rows] == sorted((r["last_visit"] for r in rows), reverse=True)


@pytest.mark.asyncio
async def test_only_the_shops_owner_may_see_them(client):  # noqa: F811
    assert (await client.get(URL, headers=auth("someone-else"))).status_code in (403, 404)
    assert (await client.get(URL)).status_code in (401, 403)
