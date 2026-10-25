"""Late cancellations and completed bookings are reported to trust_risk_service."""

import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.config import settings
from app.core import risk
from tests.test_shop_bookings_api import auth, client  # noqa: F401  (fixture)

REPORTED: list = []
REAL_REPORT = risk.report_risk


@pytest.fixture(autouse=True)
def recorded(monkeypatch):
    async def fake_report(user_id, signal_type, value, is_risk_event):
        REPORTED.append((user_id, signal_type, value, is_risk_event))

    REPORTED.clear()
    monkeypatch.setattr(risk, "report_risk", fake_report)
    return REPORTED


async def _book(http, customer: str, starts_in: timedelta) -> str:
    at = (datetime.now(timezone.utc) + starts_in).isoformat()
    resp = await http.post("/api/v1/bookings", json={"service_id": "svc-a", "scheduled_at": at}, headers=auth(customer))
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_a_customer_cancelling_within_two_hours_is_a_risk_signal(client):  # noqa: F811
    soon = await _book(client, "c7", timedelta(hours=1))
    resp = await client.post(f"/api/v1/bookings/{soon}/cancel", json={"reason": "Can't make it"}, headers=auth("c7"))
    assert resp.status_code == 200
    assert REPORTED == [("c7", "late_cancellation", 0.4, True)]


@pytest.mark.asyncio
async def test_a_late_cancellation_through_the_status_endpoint_counts_too(client):  # noqa: F811
    soon = await _book(client, "c7", timedelta(minutes=30))
    resp = await client.put(f"/api/v1/bookings/{soon}/status", json={"status": "CANCELLED"}, headers=auth("c7"))
    assert resp.status_code == 200
    assert REPORTED == [("c7", "late_cancellation", 0.4, True)]


@pytest.mark.asyncio
async def test_an_early_cancellation_or_one_by_the_shop_is_not_a_risk_signal(client):  # noqa: F811
    later = await _book(client, "c7", timedelta(days=2))
    assert (
        await client.post(f"/api/v1/bookings/{later}/cancel", json={"reason": "x"}, headers=auth("c7"))
    ).status_code == 200
    # The shop calling off a booking says nothing about the customer.
    soon = await _book(client, "c7", timedelta(hours=1))
    assert (
        await client.post(f"/api/v1/bookings/{soon}/cancel", json={"reason": "x"}, headers=auth("owner-1"))
    ).status_code == 200
    assert REPORTED == []


@pytest.mark.asyncio
async def test_a_completed_booking_is_a_safe_signal_for_the_customer(client):  # noqa: F811
    owner = auth("owner-1")
    for status in ("CONFIRMED", "IN_PROGRESS", "COMPLETED"):  # bk-4: customer c3, at the shop
        resp = await client.put("/api/v1/bookings/bk-4/status", json={"status": status}, headers=owner)
        assert resp.status_code == 200, resp.text
    assert REPORTED == [("c3", "booking_completed", 0.0, False)]


@pytest.mark.asyncio
async def test_a_dispute_resolved_as_completed_is_not_counted_twice(client):  # noqa: F811
    assert (
        await client.put("/api/v1/bookings/bk-1/status", json={"status": "DISPUTED"}, headers=auth("c1"))
    ).status_code == 200
    resolved = await client.put(
        "/api/v1/bookings/bk-1/status", json={"status": "COMPLETED"}, headers=auth("ops", "admin")
    )
    assert resolved.status_code == 200
    assert REPORTED == []


@pytest.mark.asyncio
async def test_a_trust_risk_outage_never_breaks_the_cancellation(client, monkeypatch):  # noqa: F811
    monkeypatch.setattr(risk, "report_risk", REAL_REPORT)  # the real one, against a port nothing listens on
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", "k" * 40)
    monkeypatch.setattr(settings, "TRUST_RISK_SERVICE_URL", "http://127.0.0.1:1")
    soon = await _book(client, "c7", timedelta(hours=1))
    resp = await client.post(f"/api/v1/bookings/{soon}/cancel", json={"reason": "x"}, headers=auth("c7"))
    assert resp.status_code == 200
    assert resp.json()["status"] == "CANCELLED"


@pytest.mark.asyncio
async def test_the_reporter_posts_to_the_internal_route_with_the_key(monkeypatch):
    seen = []

    def service(request: httpx.Request) -> httpx.Response:
        seen.append((request.url.raw_path.decode(), request.headers.get("x-internal-key"), json.loads(request.content)))
        return httpx.Response(200, json={})

    monkeypatch.setattr(settings, "INTERNAL_API_KEY", "k3y")
    await REAL_REPORT("c/../1", "late_cancellation", 0.4, True, transport=httpx.MockTransport(service))
    assert seen == [
        (
            "/internal/risk/c%2F%2E%2E%2F1/signals",
            "k3y",
            {"signal_type": "late_cancellation", "value": 0.4, "is_risk_event": True},
        )
    ]


@pytest.mark.asyncio
async def test_the_reporter_swallows_rejections_and_errors_and_skips_without_a_key(monkeypatch):
    calls = []

    def rejecting(request):
        calls.append(request)
        return httpx.Response(500)

    def failing(request):
        calls.append(request)
        raise httpx.ConnectError("down")

    monkeypatch.setattr(settings, "INTERNAL_API_KEY", "k3y")
    await REAL_REPORT("c1", "booking_completed", 0.0, False, transport=httpx.MockTransport(rejecting))
    await REAL_REPORT("c1", "booking_completed", 0.0, False, transport=httpx.MockTransport(failing))
    assert len(calls) == 2

    monkeypatch.setattr(settings, "INTERNAL_API_KEY", "")
    await REAL_REPORT("c1", "booking_completed", 0.0, False, transport=httpx.MockTransport(rejecting))
    assert len(calls) == 2
