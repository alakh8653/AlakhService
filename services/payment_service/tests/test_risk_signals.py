"""Failed and completed payments are reported to trust_risk_service, for the payer."""

import hashlib
import hmac
import json
import time

import httpx
import pytest

from app.config import settings
from app.core import risk
from tests.test_payment_access_api import (  # noqa: F401  (client is a fixture)
    WEBHOOK_SECRET,
    auth,
    client,
    open_checkout,
    razorpay_captured,
    sign,
)

REPORTED: list = []
REAL_REPORT = risk.report_risk


@pytest.fixture(autouse=True)
def recorded(monkeypatch):
    async def fake_report(user_id, signal_type, value, is_risk_event):
        REPORTED.append((user_id, signal_type, value, is_risk_event))

    REPORTED.clear()
    monkeypatch.setattr(risk, "report_risk", fake_report)


async def _razorpay_failed(http, pid: str, proof: dict):
    entity = {"id": "pay_x", "order_id": proof["razorpay_order_id"], "notes": {"payment_id": pid}}
    failed = json.dumps({"event": "payment.failed", "payload": {"payment": {"entity": entity}}}).encode()
    return await http.post(
        "/api/v1/webhooks/razorpay", content=failed, headers={"x-razorpay-signature": sign(WEBHOOK_SECRET, failed)}
    )


@pytest.mark.asyncio
async def test_a_verified_checkout_is_a_safe_signal_for_the_payer_once(client):  # noqa: F811
    pid, proof = await open_checkout(client, "key-risk-1")
    for _ in range(2):  # a replayed confirmation changes nothing
        assert (
            await client.post(f"/api/v1/payments/{pid}/verify", json=proof, headers=auth("cust"))
        ).status_code == 200
    assert REPORTED == [("cust", "payment_completed", 0.0, False)]


@pytest.mark.asyncio
async def test_a_capture_webhook_is_a_safe_signal_for_the_payer(client):  # noqa: F811
    pid, proof = await open_checkout(client, "key-risk-2")
    assert (await razorpay_captured(client, pid, proof)).status_code == 200
    assert REPORTED == [("cust", "payment_completed", 0.0, False)]


@pytest.mark.asyncio
async def test_a_failed_payment_is_a_risk_signal_for_the_payer(client):  # noqa: F811
    pid, proof = await open_checkout(client, "key-risk-3")
    assert (await _razorpay_failed(client, pid, proof)).status_code == 200
    assert (await _razorpay_failed(client, pid, proof)).status_code == 200  # replayed: already failed
    assert REPORTED == [("cust", "payment_failed", 0.2, True)]


@pytest.mark.asyncio
async def test_cash_confirmed_by_the_shop_is_a_safe_signal_for_the_payer(client):  # noqa: F811
    body = {"booking_id": "bk-1", "payment_method": "cash", "idempotency_key": "key-risk-4"}
    pid = (await client.post("/api/v1/payments/initiate", json=body, headers=auth("cust"))).json()["id"]
    assert (await client.post(f"/api/v1/payments/{pid}/cash-received", headers=auth("owner"))).status_code == 200
    assert REPORTED == [("cust", "payment_completed", 0.0, False)]


@pytest.mark.asyncio
async def test_a_stripe_payment_is_a_safe_signal_for_the_payer(client, monkeypatch):  # noqa: F811
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_test")
    body = {"booking_id": "bk-1", "payment_method": "cash", "idempotency_key": "key-risk-5"}
    pid = (await client.post("/api/v1/payments/initiate", json=body, headers=auth("cust"))).json()["id"]
    event = json.dumps(
        {
            "id": "evt_1",
            "object": "event",
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_1", "amount": 49900, "metadata": {"payment_id": pid}}},
        }
    )
    t = int(time.time())
    sig = hmac.new(b"whsec_test", f"{t}.{event}".encode(), hashlib.sha256).hexdigest()
    resp = await client.post("/api/v1/webhooks/stripe", content=event, headers={"stripe-signature": f"t={t},v1={sig}"})
    assert resp.status_code == 200, resp.text
    assert REPORTED == [("cust", "payment_completed", 0.0, False)]


@pytest.mark.asyncio
async def test_a_trust_risk_outage_never_breaks_the_payment(client, monkeypatch):  # noqa: F811
    monkeypatch.setattr(risk, "report_risk", REAL_REPORT)  # the real one, against a port nothing listens on
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", "k" * 40)
    monkeypatch.setattr(settings, "TRUST_RISK_SERVICE_URL", "http://127.0.0.1:1")
    pid, proof = await open_checkout(client, "key-risk-6")
    verified = await client.post(f"/api/v1/payments/{pid}/verify", json=proof, headers=auth("cust"))
    assert (verified.status_code, verified.json()["status"]) == (200, "COMPLETED")


@pytest.mark.asyncio
async def test_the_reporter_posts_to_the_internal_route_and_swallows_failures(monkeypatch):
    seen = []

    def service(request: httpx.Request) -> httpx.Response:
        seen.append((request.url.raw_path.decode(), request.headers.get("x-internal-key"), json.loads(request.content)))
        return httpx.Response(500)

    def down(request):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(settings, "INTERNAL_API_KEY", "k3y")
    await REAL_REPORT("u/../1", "payment_failed", 0.2, True, transport=httpx.MockTransport(service))
    await REAL_REPORT("u1", "payment_failed", 0.2, True, transport=httpx.MockTransport(down))
    assert seen == [
        (
            "/internal/risk/u%2F%2E%2E%2F1/signals",
            "k3y",
            {"signal_type": "payment_failed", "value": 0.2, "is_risk_event": True},
        )
    ]
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", "")
    await REAL_REPORT("u1", "payment_failed", 0.2, True, transport=httpx.MockTransport(service))
    assert len(seen) == 1
