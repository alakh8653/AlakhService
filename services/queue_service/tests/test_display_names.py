"""The shop sees the people in its queue by display name ("Ravi S."), never their contact details."""

import httpx
import pytest

from app.config import settings
from app.core import names
from app.core.names import get_name_lookup
from app.main import app
from tests.helpers import ALICE, join

CONTACT_FIELDS = {"phone", "email", "full_name", "customer_phone", "customer_email", "customer_name"}


@pytest.fixture
def named(client):
    asked = []

    async def fake_names(user_ids):
        ids = list(user_ids)
        asked.append(ids)
        return {uid: {"c1": "Ravi S."}.get(uid, "Customer") for uid in ids}

    app.dependency_overrides[get_name_lookup] = lambda: fake_names
    return asked


@pytest.mark.asyncio
async def test_the_shop_sees_display_names_only(client, named):
    qid = (await client.post("/api/v1/queues", json={"service_id": "svc-1"}, headers=ALICE)).json()["id"]
    await join(client, qid, "c1")
    await join(client, qid, "c2")

    entries = (await client.get(f"/api/v1/queues/{qid}/entries", headers=ALICE)).json()
    assert [e["customer_display_name"] for e in entries] == ["Ravi S.", "Customer"]
    assert len(named) == 1
    for e in entries:
        assert not CONTACT_FIELDS & set(e)

    called = (await client.post(f"/api/v1/queues/{qid}/next", headers=ALICE)).json()
    assert called["customer_display_name"] == "Ravi S."
    done = await client.post(f"/api/v1/queues/{qid}/entries/{called['id']}/complete", headers=ALICE)
    assert done.json()["customer_display_name"] == "Ravi S."
    second = (await client.post(f"/api/v1/queues/{qid}/next", headers=ALICE)).json()
    no_show = await client.post(f"/api/v1/queues/{qid}/entries/{second['id']}/no-show", headers=ALICE)
    assert no_show.json()["customer_display_name"] == "Customer"


@pytest.mark.asyncio
async def test_names_unavailable_reads_customer(client):
    async def broken(user_ids):
        raise RuntimeError("auth_service down")

    app.dependency_overrides[get_name_lookup] = lambda: broken
    qid = (await client.post("/api/v1/queues", json={"service_id": "svc-1"}, headers=ALICE)).json()["id"]
    await join(client, qid, "c1")
    entries = await client.get(f"/api/v1/queues/{qid}/entries", headers=ALICE)
    assert entries.status_code == 200 and entries.json()[0]["customer_display_name"] == "Customer"


@pytest.mark.asyncio
async def test_the_lookup_asks_auth_service_with_the_internal_key(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", "k" * 40)
    monkeypatch.setattr(names, "_cache", {})

    def handler(request: httpx.Request):
        assert request.url.path == "/internal/users/display-names"
        assert request.headers["X-Internal-Key"] == "k" * 40
        return httpx.Response(200, json={"names": {"c1": "Ravi S."}})

    found = await names.fetch_display_names(["c1", "c2"], transport=httpx.MockTransport(handler))
    assert found == {"c1": "Ravi S.", "c2": "Customer"}
