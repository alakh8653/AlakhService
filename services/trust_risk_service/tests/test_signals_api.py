"""Signals reported by other services, the admin batch lookup, and input validation."""

import pytest

from app.config import settings
from tests.test_access_rules import ADMIN, ALICE, client  # noqa: F401  (fixture)

KEY = "k" * 40
INTERNAL = {"X-Internal-Key": KEY}


@pytest.fixture
def internal_key(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", KEY)


def _risk(signal_type="no_show", value=0.5, risky=True):
    return {"signal_type": signal_type, "value": value, "is_risk_event": risky}


@pytest.mark.asyncio
async def test_a_service_with_the_internal_key_can_report_a_signal(client, internal_key):  # noqa: F811
    resp = await client.post("/internal/risk/alice/signals", json=_risk(), headers=INTERNAL)
    assert resp.status_code == 200
    assert resp.json()["user_id"] == "alice"
    assert resp.json()["risk_events"] == 1

    history = await client.get("/api/v1/risk/alice/history", headers=ADMIN)
    assert [(s["signal_type"], s["value"]) for s in history.json()] == [("no_show", 0.5)]


@pytest.mark.asyncio
async def test_internal_signals_need_the_right_key(client, internal_key):  # noqa: F811
    assert (await client.post("/internal/risk/alice/signals", json=_risk())).status_code == 401
    wrong = {"X-Internal-Key": "x" * 40}
    assert (await client.post("/internal/risk/alice/signals", json=_risk(), headers=wrong)).status_code == 401
    # A user's own token is not an internal key.
    assert (await client.post("/internal/risk/alice/signals", json=_risk(), headers=ALICE)).status_code == 401


@pytest.mark.asyncio
async def test_internal_signals_are_off_when_no_key_is_configured(client, monkeypatch):  # noqa: F811
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", "")
    resp = await client.post("/internal/risk/alice/signals", json=_risk(), headers={"X-Internal-Key": ""})
    assert resp.status_code == 503


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        _risk(value=1.5),
        _risk(value=-1.0),
        _risk(signal_type=""),
        _risk(signal_type="x" * 51),
    ],
)
async def test_signal_values_and_types_are_validated_on_both_apis(client, internal_key, body):  # noqa: F811
    assert (await client.post("/internal/risk/alice/signals", json=body, headers=INTERNAL)).status_code == 422
    assert (await client.post("/api/v1/risk/alice/signal", json=body, headers=ADMIN)).status_code == 422


@pytest.mark.asyncio
async def test_batch_lookup_returns_only_users_who_have_a_profile(client, internal_key):  # noqa: F811
    await client.post("/internal/risk/alice/signals", json=_risk(), headers=INTERNAL)
    await client.post("/internal/risk/bob/signals", json=_risk("booking_completed", 0.0, False), headers=INTERNAL)

    resp = await client.post("/api/v1/risk/levels", json={"user_ids": ["alice", "bob", "carol"]}, headers=ADMIN)
    assert resp.status_code == 200
    levels = {p["user_id"]: p["risk_level"] for p in resp.json()}
    assert set(levels) == {"alice", "bob"}

    # Looking a user up does not create a profile for them.
    again = await client.post("/api/v1/risk/levels", json={"user_ids": ["carol"]}, headers=ADMIN)
    assert again.json() == []


@pytest.mark.asyncio
async def test_batch_lookup_is_admin_only_and_capped(client):  # noqa: F811
    body = {"user_ids": ["alice"]}
    assert (await client.post("/api/v1/risk/levels", json=body)).status_code == 401
    assert (await client.post("/api/v1/risk/levels", json=body, headers=ALICE)).status_code == 403
    too_many = {"user_ids": [f"u{i}" for i in range(201)]}
    assert (await client.post("/api/v1/risk/levels", json=too_many, headers=ADMIN)).status_code == 422
    assert (await client.post("/api/v1/risk/levels", json={"user_ids": []}, headers=ADMIN)).json() == []
