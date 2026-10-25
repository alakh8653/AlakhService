"""A dispute is not a way round the platform: the other party reads it with contact details hidden."""

import pytest

from tests.test_dispute_api import B1, auth, client  # noqa: F401  (the fixture)

CUSTOMER, OWNER = auth("cust-1", "user"), auth("owner-1", "user")
MASK = "[hidden for your safety]"


@pytest.mark.asyncio
async def test_the_other_party_reads_disputes_without_contact_details(client):  # noqa: F811
    created = await client.post(
        "/api/v1/disputes",
        json={"booking_id": B1, "dispute_type": "service_quality", "description": "Bad cut. Call me on 9876543210"},
        headers=CUSTOMER,
    )
    dispute_id = created.json()["id"]
    url = f"/api/v1/disputes/{dispute_id}"
    assert (await client.get(url, headers=OWNER)).json()["description"] == f"Bad cut. Call me on {MASK}"
    assert (await client.get(url, headers=CUSTOMER)).json()["description"].endswith("9876543210")
    assert (await client.get(url)).json()["description"].endswith("9876543210")  # admins see it as written

    await client.post(
        f"{url}/messages", json={"author_id": "owner-1", "content": "Mail us at shop@gmail.com"}, headers=OWNER
    )
    to_customer = (await client.get(f"{url}/messages", headers=CUSTOMER)).json()
    assert to_customer[0]["content"] == f"Mail us at {MASK}"
    assert (await client.get(f"{url}/messages", headers=OWNER)).json()[0]["content"].endswith("gmail.com")
    assert (await client.get(f"{url}/messages")).json()[0]["content"].endswith("gmail.com")
