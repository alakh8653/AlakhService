"""booking_service alerts every admin of an SOS: it finds them through an internal route that gives ids only."""

import pytest
from sqlalchemy import update

from app.database import get_db
from app.main import app
from app.models.user import User
from tests.test_accounts_api import KEY, bearer, client  # noqa: F401  (the fixture)

URL = "/internal/users/admins"


async def _set(**values):
    async for db in app.dependency_overrides[get_db]():
        await db.execute(update(User).where(User.email == values.pop("email")).values(**values))


@pytest.mark.asyncio
async def test_lists_active_admin_ids_only_with_the_internal_key(client):  # noqa: F811
    assert (await client.get(URL, headers={"X-Internal-Key": KEY})).json() == {"user_ids": []}
    await _set(email="ravi@example.com", role="admin")
    await _set(email="asha@example.com", role="admin", is_active=False)
    resp = await client.get(URL, headers={"X-Internal-Key": KEY})
    assert resp.status_code == 200
    ids = resp.json()["user_ids"]
    assert len(ids) == 1 and "@" not in resp.text  # no contact details, and banned admins are left out
    assert (await client.get(URL)).status_code == 401
    assert (await client.get(URL, headers=bearer("ops", "admin"))).status_code == 401
    assert (await client.get("/api/v1" + URL, headers={"X-Internal-Key": KEY})).status_code == 404
