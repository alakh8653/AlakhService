"""An owner whose sign-in has expired hears so, rather than being told their shop in review does not exist."""

from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from app.config import settings
from tests import test_reviews_api
from tests.test_reviews_api import auth

client = test_reviews_api.client
OWNER = auth("owner-1")


def expired(sub="owner-1"):
    token = jwt.encode(
        {"sub": sub, "type": "access", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return {"Authorization": f"Bearer {token}"}


async def shop_in_review(client):
    resp = await client.post(
        "/api/v1/shops", json={"owner_id": "owner-1", "name": "In review", "category": "salon"}, headers=OWNER
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_an_expired_token_is_a_401_so_the_app_renews_it(client):
    shop_id = await shop_in_review(client)
    for path in ("/api/v1/shops?owner_id=owner-1", f"/api/v1/shops/{shop_id}", "/api/v1/shops/search?q=review"):
        assert (await client.get(path, headers=expired())).status_code == 401, path


@pytest.mark.asyncio
async def test_with_a_fresh_token_the_owner_sees_their_shop_in_review(client):
    shop_id = await shop_in_review(client)
    listed = await client.get("/api/v1/shops?owner_id=owner-1", headers=OWNER)
    assert [s["id"] for s in listed.json()] == [shop_id]
    assert (await client.get(f"/api/v1/shops/{shop_id}", headers=OWNER)).status_code == 200


@pytest.mark.asyncio
async def test_visitors_with_no_token_are_unaffected(client):
    shop_id = await shop_in_review(client)
    assert (await client.get("/api/v1/shops")).status_code == 200
    # A shop in review stays hidden from them.
    assert (await client.get(f"/api/v1/shops/{shop_id}")).status_code == 404
    assert (await client.get("/api/v1/shops?owner_id=owner-1")).json() == []


@pytest.mark.asyncio
async def test_a_refresh_token_does_not_count_as_signed_in(client):
    token = jwt.encode({"sub": "owner-1", "type": "refresh"}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    headers = {"Authorization": f"Bearer {token}"}
    assert (await client.get("/api/v1/shops", headers=headers)).status_code == 401
