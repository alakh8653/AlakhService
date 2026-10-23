"""Signed-in devices, sign-outs that reach the gateway, lockouts that can't be used against others."""

import time
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.core.security import decode_token, describe_device
from app.database import Base, get_db
from app.dependencies import get_redis
from app.main import app
from app.models.user import OTPCode, RefreshToken

KEY = "internal-test-key"
PASSWORD = "Passw0rd!"
CHROME = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36"
PHONE = "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/130.0 Mobile Safari/537.36"


class FakeRedis:
    """The Redis commands auth_service uses, with expiry times recorded (not enforced)."""

    def __init__(self):
        self.store, self.ttls = {}, {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ex=None):
        self.store[key] = value
        self.ttls[key] = ex

    async def setex(self, key, ttl, value):
        await self.set(key, value, ex=ttl)

    async def incr(self, key):
        self.store[key] = int(self.store.get(key, 0)) + 1
        return self.store[key]

    async def expire(self, key, ttl):
        self.ttls[key] = ttl

    async def ttl(self, key):
        return self.ttls.get(key) or -1

    async def delete(self, key):
        self.store.pop(key, None)


@pytest_asyncio.fixture
async def env(monkeypatch):
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

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_redis
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (
            await client.post(
                "/api/v1/auth/register",
                json={
                    "email": "Ravi@Example.com",
                    "password": PASSWORD,
                    "full_name": "Ravi",
                    "accepted_terms_version": "2026-10",
                },
            )
        ).status_code == 201
        yield client, redis, factory
    app.dependency_overrides.clear()
    await engine.dispose()


async def login(client, ua=CHROME, ip="203.0.113.5", password=PASSWORD, email="ravi@example.com"):
    return await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"user-agent": ua, "x-real-ip": ip},
    )


def auth(tokens) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.mark.asyncio
async def test_emails_are_one_account_whatever_their_case(env):
    client, _, _ = env
    assert (await login(client, email="RAVI@example.COM")).status_code == 200
    again = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "ravi@EXAMPLE.com",
            "password": PASSWORD,
            "full_name": "Copy",
            "accepted_terms_version": "2026-10",
        },
    )
    assert again.status_code == 409
    me = (await client.get("/api/v1/auth/me", headers=auth((await login(client)).json()))).json()
    assert me["email"] == "ravi@example.com"


@pytest.mark.asyncio
async def test_people_see_their_devices_and_can_sign_one_out(env):
    client, redis, _ = env
    laptop = (await login(client)).json()
    phone = (await login(client, ua=PHONE, ip="198.51.100.7")).json()

    sessions = (await client.get("/api/v1/auth/sessions", headers=auth(laptop))).json()
    assert [(s["device"], s["ip_address"], s["current"]) for s in sessions] == [
        ("Chrome on Android", "198.51.100.7", False),
        ("Chrome on Windows", "203.0.113.5", True),
    ]
    # A refresh keeps the same session (and when it started).
    refreshed = (
        await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": phone["refresh_token"]}, headers={"user-agent": PHONE}
        )
    ).json()
    after = (await client.get("/api/v1/auth/sessions", headers=auth(laptop))).json()
    assert {s["id"] for s in after} == {s["id"] for s in sessions}

    phone_sid = decode_token(refreshed["access_token"])["sid"]
    assert (await client.delete(f"/api/v1/auth/sessions/{phone_sid}", headers=auth(laptop))).status_code == 200
    # Its refresh token is dead and the gateway is told to refuse its access tokens.
    assert (
        await client.post("/api/v1/auth/refresh", json={"refresh_token": refreshed["refresh_token"]})
    ).status_code == 401
    assert redis.store[f"auth:revoked_sid:{phone_sid}"] == "1"
    assert redis.ttls[f"auth:revoked_sid:{phone_sid}"] >= settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    assert len((await client.get("/api/v1/auth/sessions", headers=auth(laptop))).json()) == 1
    # Nobody can end another person's session.
    assert (await client.delete("/api/v1/auth/sessions/not-mine", headers=auth(laptop))).status_code == 404


@pytest.mark.asyncio
async def test_signing_out_stops_access_tokens_too(env):
    client, redis, _ = env
    tokens = (await login(client)).json()
    sid = decode_token(tokens["access_token"])["sid"]
    out = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]}, headers=auth(tokens)
    )
    assert out.status_code == 200
    assert f"auth:revoked_sid:{sid}" in redis.store

    tokens = (await login(client)).json()
    issued = decode_token(tokens["access_token"])["iat"]
    before = time.time()
    assert (await client.post("/api/v1/auth/logout-all", headers=auth(tokens))).status_code == 200
    user_id = decode_token(tokens["access_token"])["sub"]
    marker = float(redis.store[f"auth:revoked_before:{user_id}"])
    # Every token issued so far is older than the marker; a new sign-in afterwards is not.
    assert issued < marker and marker >= before - 1
    later = (await login(client)).json()
    assert decode_token(later["access_token"])["iat"] >= marker


@pytest.mark.asyncio
async def test_a_ban_stops_the_access_tokens_already_issued(env):
    client, redis, _ = env
    tokens = (await login(client)).json()
    user_id = decode_token(tokens["access_token"])["sub"]
    banned = await client.post(
        f"/internal/users/{user_id}/status", json={"is_active": False}, headers={"X-Internal-Key": KEY}
    )
    assert banned.status_code == 200
    assert float(redis.store[f"auth:revoked_before:{user_id}"]) > decode_token(tokens["access_token"])["iat"]


@pytest.mark.asyncio
async def test_a_reused_refresh_token_ends_the_session(env):
    client, redis, factory = env
    first = (await login(client)).json()
    second = (await client.post("/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]})).json()
    sid = decode_token(second["access_token"])["sid"]

    # A parallel retry moments later is turned away but does no harm.
    retry = await client.post("/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert retry.status_code == 401
    assert f"auth:revoked_sid:{sid}" not in redis.store

    # Replayed later (someone kept a copy): the whole session ends, including the newer token.
    async with factory() as db:
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.session_id == sid, RefreshToken.is_revoked == True)  # noqa: E712
            .values(revoked_at=datetime.now(timezone.utc) - timedelta(minutes=5))
        )
        await db.commit()
    replay = await client.post("/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert replay.status_code == 401
    assert f"auth:revoked_sid:{sid}" in redis.store
    assert (
        await client.post("/api/v1/auth/refresh", json={"refresh_token": second["refresh_token"]})
    ).status_code == 401


@pytest.mark.asyncio
async def test_failed_sign_ins_lock_out_that_network_only(env):
    client, redis, _ = env
    for _ in range(settings.MAX_LOGIN_ATTEMPTS):
        assert (await login(client, password="Wrong1234")).status_code == 401
    locked = await login(client)
    assert locked.status_code == 429
    assert str(settings.LOCKOUT_DURATION_SECONDS) in locked.json()["detail"]
    # The real owner, signing in from home, is not locked out by someone else's guesses.
    assert (await login(client, ip="198.51.100.7")).status_code == 200
    assert redis.ttls["auth:locked:ravi@example.com:203.0.113.5"] == settings.LOCKOUT_DURATION_SECONDS


@pytest.mark.asyncio
async def test_guessing_from_many_networks_locks_the_account_for_a_while(env):
    client, _, _ = env
    for i in range(20):
        await login(client, password="Wrong1234", ip=f"192.0.2.{i}")
    assert (await login(client, ip="198.51.100.7")).status_code == 429


@pytest.mark.asyncio
async def test_wrong_codes_are_counted(env, monkeypatch):
    client, _, factory = env
    sent = await client.post("/api/v1/auth/send-otp", json={"phone_or_email": "ravi@example.com", "purpose": "login"})
    assert sent.status_code == 200
    verify = {"phone_or_email": "RAVI@example.com", "code": "000000", "purpose": "login"}
    for _ in range(5):
        wrong = await client.post("/api/v1/auth/verify-otp", json=verify)
        assert wrong.json()["detail"] == "Invalid OTP"
    async with factory() as db:
        otp = (await db.execute(select(OTPCode))).scalars().first()
    assert otp.attempts == 5
    # After five wrong guesses the code is dead, whatever is tried next.
    last = await client.post("/api/v1/auth/verify-otp", json=verify)
    assert "too many" in last.json()["detail"].lower()


def test_devices_are_described_in_plain_words():
    assert describe_device(CHROME) == "Chrome on Windows"
    assert describe_device(PHONE) == "Chrome on Android"
    assert describe_device("Dart/3.5 (dart:io)") == "Alakh app"
    assert describe_device(None) == "Unknown browser"
