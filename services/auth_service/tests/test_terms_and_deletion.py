"""Sign-up records acceptance of the Terms; accounts can be deleted from the web with a one-time code;
codes can be texted through MSG91 with a DLT template."""

import json

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.core import consent, mailer, sms
from app.database import Base, get_db
from app.dependencies import get_redis
from app.main import app
from app.routers import auth as auth_router
from app.routers.users import get_profile_eraser

KEY = "internal-test-key"
EMAIL = "ravi@example.com"
PASSWORD = "Passw0rd!"


class FakeRedis:
    def __init__(self):
        self.store = {}

    async def get(self, key):
        return self.store.get(key)

    async def incr(self, key):
        self.store[key] = int(self.store.get(key, 0)) + 1
        return self.store[key]

    async def expire(self, key, ttl):
        return True

    async def delete(self, key):
        self.store.pop(key, None)

    async def ttl(self, key):
        return -1

    async def setex(self, key, ttl, value):
        self.store[key] = value


@pytest_asyncio.fixture
async def client(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", KEY)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    redis = FakeRedis()

    async def override_get_db():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def override_redis():
        yield redis

    consents, codes, erased = [], [], []

    async def fake_consent(*args):
        consents.append(args)

    async def fake_send_code(user_id, destination, code, purpose):
        codes.append((destination, code, purpose))

    async def fake_erase(token):
        erased.append(token)

    monkeypatch.setattr(auth_router, "record_terms_consent", fake_consent)
    monkeypatch.setattr(auth_router, "send_otp_code", fake_send_code)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_redis
    app.dependency_overrides[get_profile_eraser] = lambda: fake_erase
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        ac.consents, ac.codes, ac.erased = consents, codes, erased
        yield ac
    app.dependency_overrides.clear()
    await engine.dispose()


def account(**extra):
    return {"email": EMAIL, "password": PASSWORD, "full_name": "Ravi Kumar", **extra}


@pytest.mark.asyncio
async def test_registering_requires_accepting_the_terms(client):
    for body in (account(), account(accepted_terms_version="  ")):
        resp = await client.post("/api/v1/auth/register", json=body)
        assert (resp.status_code, resp.json()) == (422, {"detail": "Please accept the Terms and Privacy Policy"})
    assert client.consents == []

    resp = await client.post(
        "/api/v1/auth/register",
        json=account(accepted_terms_version="2026-10"),
        headers={"user-agent": "AlakhApp/1.0", "x-real-ip": "203.0.113.9"},
    )
    assert resp.status_code == 201
    user = resp.json()
    assert user["accepted_terms_version"] == "2026-10" and user["accepted_terms_at"]
    # The acceptance also goes to the consent register, with the person's address as evidence.
    assert client.consents == [(user["id"], "2026-10", "203.0.113.9", "AlakhApp/1.0")]


@pytest.mark.asyncio
async def test_signed_in_people_accept_newer_terms(client):
    await client.post("/api/v1/auth/register", json=account(accepted_terms_version="2026-10"))
    tokens = (await client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})).json()
    me = {"Authorization": f"Bearer {tokens['access_token']}"}
    assert (await client.post("/api/v1/auth/accept-terms", json={"accepted_terms_version": "2027-01"})).status_code in (
        401,
        403,
    )
    resp = await client.post("/api/v1/auth/accept-terms", json={"accepted_terms_version": "2027-01"}, headers=me)
    assert resp.json()["accepted_terms_version"] == "2027-01"
    assert (await client.get("/api/v1/auth/me", headers=me)).json()["accepted_terms_version"] == "2027-01"
    assert [c[1] for c in client.consents] == ["2026-10", "2027-01"]


@pytest.mark.asyncio
async def test_the_current_legal_documents_are_public(client, monkeypatch):
    monkeypatch.setattr(settings, "LEGAL_BASE_URL", "https://alakh.example.in/")
    monkeypatch.setattr(settings, "TERMS_VERSION", "2026-10")
    resp = await client.get("/api/v1/legal/current")
    assert resp.status_code == 200
    assert resp.json() == {
        "terms_version": "2026-10",
        "privacy_url": "https://alakh.example.in/privacy",
        "terms_url": "https://alakh.example.in/terms",
        "refund_url": "https://alakh.example.in/refunds",
        "grievance_url": "https://alakh.example.in/grievance",
    }


@pytest.mark.asyncio
async def test_an_account_is_deleted_with_a_one_time_code_without_signing_in(client):
    user = (await client.post("/api/v1/auth/register", json=account(accepted_terms_version="2026-10"))).json()
    send = await client.post(
        "/api/v1/auth/send-otp", json={"phone_or_email": "Ravi@Example.com", "purpose": "delete_account"}
    )
    assert send.status_code == 200
    [(destination, code, purpose)] = client.codes
    assert (destination, purpose) == (EMAIL, "delete_account")

    url = "/api/v1/auth/delete-account/otp"
    wrong = "000000" if code != "000000" else "111111"
    assert (await client.post(url, json={"phone_or_email": EMAIL, "code": wrong})).status_code == 401
    # A deletion code does nothing at the sign-in endpoint.
    assert (
        await client.post(
            "/api/v1/auth/verify-otp", json={"phone_or_email": EMAIL, "code": code, "purpose": "delete_account"}
        )
    ).status_code == 422

    deleted = await client.post(url, json={"phone_or_email": EMAIL, "code": code})
    assert deleted.status_code == 200
    # The profile was erased as the person (a short-lived token for their account).
    [token] = client.erased
    assert jwt.get_unverified_claims(token)["sub"] == user["id"]
    assert (await client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})).status_code == 401
    # The code is spent, and the email is free for a new account.
    assert (await client.post(url, json={"phone_or_email": EMAIL, "code": code})).status_code == 401
    assert (
        await client.post("/api/v1/auth/register", json=account(accepted_terms_version="2026-10"))
    ).status_code == 201


@pytest.mark.asyncio
async def test_deletion_attempts_are_rate_limited(client):
    await client.post("/api/v1/auth/register", json=account(accepted_terms_version="2026-10"))
    url = "/api/v1/auth/delete-account/otp"
    for _ in range(settings.DELETE_ACCOUNT_ATTEMPTS_PER_WINDOW):
        assert (await client.post(url, json={"phone_or_email": EMAIL, "code": "123456"})).status_code == 401
    assert (await client.post(url, json={"phone_or_email": EMAIL, "code": "123456"})).status_code == 429
    # Unknown accounts answer the same as wrong codes.
    assert (await client.post(url, json={"phone_or_email": "x@example.com", "code": "123456"})).status_code == 401


@pytest.mark.asyncio
async def test_consents_go_to_the_compliance_service_and_failures_are_swallowed(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", KEY)
    seen = []

    def compliance(request: httpx.Request) -> httpx.Response:
        seen.append((request.url.path, request.headers["x-internal-key"], json.loads(request.content)))
        return httpx.Response(201, json={})

    await consent.record_terms_consent("u1", "2026-10", "203.0.113.9", "App", transport=httpx.MockTransport(compliance))
    assert [(path, key, body["consent_type"], body["version"]) for path, key, body in seen] == [
        ("/internal/consent", KEY, "terms_of_service", "2026-10"),
        ("/internal/consent", KEY, "privacy_policy", "2026-10"),
    ]
    assert seen[0][2]["ip_address"] == "203.0.113.9"

    def down(request):
        raise httpx.ConnectError("refused")

    await consent.record_terms_consent("u1", "2026-10", None, None, transport=httpx.MockTransport(down))


@pytest.mark.asyncio
async def test_msg91_sends_the_otp_with_its_dlt_template(monkeypatch):
    monkeypatch.setattr(settings, "MSG91_AUTH_KEY", "msg91-key")
    monkeypatch.setattr(settings, "MSG91_SENDER_ID", "ALAKHS")
    monkeypatch.setattr(settings, "MSG91_OTP_TEMPLATE_ID", "1107160000000000001")
    calls = []

    def msg91(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"type": "success", "message": "3763"})

    await sms.send_msg91("+919876543210", "Your code is 1", "1107160000000000001", transport=httpx.MockTransport(msg91))
    [call] = calls
    assert call.headers["authkey"] == "msg91-key"
    assert json.loads(call.content) == {
        "sender": "ALAKHS",
        "route": "4",
        "country": "91",
        "DLT_TE_ID": "1107160000000000001",
        "sms": [{"message": "Your code is 1", "to": ["919876543210"]}],
    }

    def refused(request):
        return httpx.Response(200, json={"type": "error", "message": "Template mismatch"})

    with pytest.raises(RuntimeError):
        await sms.send_msg91("+919876543210", "x", "t", transport=httpx.MockTransport(refused))


@pytest.mark.asyncio
async def test_sms_provider_picks_who_texts_the_code(monkeypatch):
    sent = []

    async def fake_msg91(to, body, template_id):
        sent.append(("msg91", to, body, template_id))

    async def fake_twilio(to, body):
        sent.append(("twilio", to, body))

    monkeypatch.setattr(sms, "send_msg91", fake_msg91)
    monkeypatch.setattr(sms, "send_twilio", fake_twilio)
    monkeypatch.setattr(settings, "SMS_PROVIDER", "msg91")
    monkeypatch.setattr(settings, "MSG91_AUTH_KEY", "k")
    monkeypatch.setattr(settings, "MSG91_SENDER_ID", "ALAKHS")
    monkeypatch.setattr(settings, "MSG91_OTP_TEMPLATE_ID", "1107")
    monkeypatch.setattr(settings, "OTP_EXPIRE_SECONDS", 300)

    await mailer.send_otp_code("u1", "+919876543210", "482913", "login")
    assert sent == [
        ("msg91", "+919876543210", "Your AlakhService code is 482913. It expires in 5 minutes. Never share it.", "1107")
    ]

    sent.clear()
    monkeypatch.setattr(settings, "MSG91_OTP_TEMPLATE_ID", "")  # MSG91 without a template: nothing is sent
    await mailer.send_otp_code("u1", "+919876543210", "482913", "login")
    monkeypatch.setattr(settings, "SMS_PROVIDER", "none")
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "AC1")
    monkeypatch.setattr(settings, "TWILIO_FROM_NUMBER", "+15550000000")
    await mailer.send_otp_code("u1", "+919876543210", "482913", "login")
    assert sent == []

    monkeypatch.setattr(settings, "SMS_PROVIDER", "twilio")
    await mailer.send_otp_code("u1", "+919876543210", "482913", "login")
    assert [s[0] for s in sent] == ["twilio"]
