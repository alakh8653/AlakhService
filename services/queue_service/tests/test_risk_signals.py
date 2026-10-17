"""Customers who are called and never turn up are reported to trust_risk_service."""

import json

import httpx
import pytest

from app.config import settings
from app.core import risk
from tests.helpers import ALICE, join
from tests.test_wait_and_lifecycle import backdate_call, open_queue

REPORTED: list = []
REAL_REPORT = risk.report_risk


@pytest.fixture(autouse=True)
def recorded(monkeypatch):
    async def fake_report(user_id, signal_type, value, is_risk_event):
        REPORTED.append((user_id, signal_type, value, is_risk_event))

    REPORTED.clear()
    monkeypatch.setattr(risk, "report_risk", fake_report)


@pytest.mark.asyncio
async def test_a_no_show_marked_by_the_shop_is_a_risk_signal(client):
    q = await open_queue(client)
    await join(client, q["id"], "c1")
    called = (await client.post(f"/api/v1/queues/{q['id']}/next", headers=ALICE)).json()
    assert REPORTED == []  # being called is not a signal

    resp = await client.post(f"/api/v1/queues/{q['id']}/entries/{called['id']}/no-show", headers=ALICE)
    assert resp.status_code == 200
    assert REPORTED == [("c1", "no_show", 0.5, True)]
    # A refused mark (no longer called) reports nothing more.
    await client.post(f"/api/v1/queues/{q['id']}/entries/{called['id']}/no-show", headers=ALICE)
    assert len(REPORTED) == 1


@pytest.mark.asyncio
async def test_a_no_show_skipped_after_the_grace_period_is_a_risk_signal(client):
    q = await open_queue(client, no_show_grace_minutes=10)
    for who in ("c1", "c2"):
        await join(client, q["id"], who)
    first = (await client.post(f"/api/v1/queues/{q['id']}/next", headers=ALICE)).json()
    await backdate_call(first["id"], 11)
    second = (await client.post(f"/api/v1/queues/{q['id']}/next", headers=ALICE)).json()
    assert second["customer_id"] == "c2"
    assert REPORTED == [("c1", "no_show", 0.5, True)]


@pytest.mark.asyncio
async def test_a_served_customer_is_not_reported(client):
    q = await open_queue(client)
    await join(client, q["id"], "c1")
    called = (await client.post(f"/api/v1/queues/{q['id']}/next", headers=ALICE)).json()
    await client.post(f"/api/v1/queues/{q['id']}/entries/{called['id']}/complete", headers=ALICE)
    assert REPORTED == []


@pytest.mark.asyncio
async def test_a_trust_risk_outage_never_breaks_marking_a_no_show(client, monkeypatch):
    monkeypatch.setattr(risk, "report_risk", REAL_REPORT)  # the real one, against a port nothing listens on
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", "k" * 40)
    monkeypatch.setattr(settings, "TRUST_RISK_SERVICE_URL", "http://127.0.0.1:1")
    q = await open_queue(client)
    await join(client, q["id"], "c1")
    called = (await client.post(f"/api/v1/queues/{q['id']}/next", headers=ALICE)).json()
    resp = await client.post(f"/api/v1/queues/{q['id']}/entries/{called['id']}/no-show", headers=ALICE)
    assert (resp.status_code, resp.json()["status"]) == (200, "NO_SHOW")


@pytest.mark.asyncio
async def test_the_reporter_posts_to_the_internal_route_and_swallows_failures(monkeypatch):
    seen = []

    def service(request: httpx.Request) -> httpx.Response:
        seen.append((request.url.raw_path.decode(), request.headers.get("x-internal-key"), json.loads(request.content)))
        return httpx.Response(503)

    def down(request):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(settings, "INTERNAL_API_KEY", "k3y")
    await REAL_REPORT("c/1", "no_show", 0.5, True, transport=httpx.MockTransport(service))
    await REAL_REPORT("c1", "no_show", 0.5, True, transport=httpx.MockTransport(down))
    assert seen == [
        ("/internal/risk/c%2F1/signals", "k3y", {"signal_type": "no_show", "value": 0.5, "is_risk_event": True})
    ]
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", "")
    await REAL_REPORT("c1", "no_show", 0.5, True, transport=httpx.MockTransport(service))
    assert len(seen) == 1
