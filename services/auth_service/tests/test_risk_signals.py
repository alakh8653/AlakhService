"""A sign-in lockout on a real account is reported to trust_risk_service."""

import json

import httpx
import pytest
from sqlalchemy import select

from app.config import settings
from app.core import risk
from app.models.user import User
from tests.test_sessions_and_lockout import env, login  # noqa: F401  (env is a fixture)

REPORTED: list = []
REAL_REPORT = risk.report_risk


@pytest.fixture(autouse=True)
def recorded(monkeypatch):
    async def fake_report(user_id, signal_type, value, is_risk_event):
        REPORTED.append((user_id, signal_type, value, is_risk_event))

    REPORTED.clear()
    monkeypatch.setattr(risk, "report_risk", fake_report)


async def _ravi_id(factory) -> str:
    async with factory() as db:
        return (await db.execute(select(User.id).where(User.email == "ravi@example.com"))).scalar_one()


@pytest.mark.asyncio
async def test_a_lockout_is_a_risk_signal_for_the_account(env):  # noqa: F811
    client, _, factory = env
    for _ in range(settings.MAX_LOGIN_ATTEMPTS - 1):
        assert (await login(client, password="Wrong1234")).status_code == 401
    assert REPORTED == []  # failures short of a lockout are not reported

    locking = await login(client, password="Wrong1234")
    assert (locking.status_code, locking.json()) == (401, {"detail": "Invalid credentials"})
    assert REPORTED == [(await _ravi_id(factory), "login_lockout", 0.3, True)]
    assert (await login(client)).status_code == 429  # and the lockout itself still holds


@pytest.mark.asyncio
async def test_a_lockout_on_an_unknown_identifier_is_not_reported(env):  # noqa: F811
    client, _, _ = env
    for _ in range(settings.MAX_LOGIN_ATTEMPTS):
        assert (await login(client, password="Wrong1234", email="nobody@example.com")).status_code == 401
    assert (await login(client, email="nobody@example.com")).status_code == 429
    assert REPORTED == []


@pytest.mark.asyncio
async def test_a_trust_risk_outage_never_changes_the_sign_in_answer(env, monkeypatch):  # noqa: F811
    client, _, _ = env
    monkeypatch.setattr(risk, "report_risk", REAL_REPORT)  # the real one, against a port nothing listens on
    monkeypatch.setattr(settings, "TRUST_RISK_SERVICE_URL", "http://127.0.0.1:1")
    for _ in range(settings.MAX_LOGIN_ATTEMPTS):
        assert (await login(client, password="Wrong1234")).status_code == 401
    assert (await login(client)).status_code == 429


@pytest.mark.asyncio
async def test_the_reporter_posts_to_the_internal_route_and_swallows_failures(monkeypatch):
    seen = []

    def service(request: httpx.Request) -> httpx.Response:
        seen.append((request.url.raw_path.decode(), request.headers.get("x-internal-key"), json.loads(request.content)))
        return httpx.Response(401)

    def down(request):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(settings, "INTERNAL_API_KEY", "k3y")
    await REAL_REPORT("u1", "login_lockout", 0.3, True, transport=httpx.MockTransport(service))
    await REAL_REPORT("u1", "login_lockout", 0.3, True, transport=httpx.MockTransport(down))
    assert seen == [
        ("/internal/risk/u1/signals", "k3y", {"signal_type": "login_lockout", "value": 0.3, "is_risk_event": True})
    ]
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", "")
    await REAL_REPORT("u1", "login_lockout", 0.3, True, transport=httpx.MockTransport(service))
    assert len(seen) == 1
