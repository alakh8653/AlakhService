"""Phone sign-in and one-time codes: delivered (never logged), rate limited, no account probing."""
import os
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from structlog.testing import capture_logs

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from app.config import settings  # noqa: E402
from app.core import mailer  # noqa: E402
from app.core.exceptions import InvalidCredentialsError, OTPInvalidError, OTPRateLimitedError  # noqa: E402
from app.database import Base  # noqa: E402
from app.routers.auth import send_otp, verify_otp  # noqa: E402
from app.schemas.auth import OTPRequest, OTPVerify, UserCreate, UserLogin  # noqa: E402
from app.services.auth_service import AuthService  # noqa: E402

service = AuthService()
PHONE = "+919876543210"


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


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)() as session:
        await service.register(session, UserCreate(phone=PHONE, password="Password1", full_name="Phone User"))
        yield session
    await engine.dispose()


@pytest.fixture
def request_():
    req = MagicMock()
    req.client.host = "127.0.0.1"
    req.headers = {"user-agent": "test-agent"}
    return req


async def request_code(db, redis, identifier, purpose="login"):
    background = BackgroundTasks()
    await send_otp(OTPRequest(phone_or_email=identifier, purpose=purpose), background, db=db, redis=redis)
    return background


async def deliver(background, monkeypatch):
    """Run the background delivery with SMS configured, returning the texts sent."""
    sent = []

    async def fake_sms(to, body):
        sent.append((to, body))

    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "AC123")
    monkeypatch.setattr(settings, "TWILIO_FROM_NUMBER", "+15550000000")
    monkeypatch.setattr(mailer, "_send_sms", fake_sms)
    await background()
    return sent


@pytest.mark.asyncio
async def test_phone_accounts_can_sign_in_with_a_password(db, request_):
    tokens = await service.login(db, FakeRedis(), UserLogin(phone=PHONE, password="Password1"), request_)
    assert tokens.access_token and tokens.refresh_token
    with pytest.raises(InvalidCredentialsError):
        await service.login(db, FakeRedis(), UserLogin(phone=PHONE, password="Wrong1234"), request_)
    with pytest.raises(ValueError):
        UserLogin(password="Password1")


@pytest.mark.asyncio
async def test_codes_are_texted_never_logged_and_unknown_numbers_look_the_same(db, monkeypatch):
    redis = FakeRedis()
    with capture_logs() as logs:
        unknown = await request_code(db, redis, "+910000000000")
        known = await request_code(db, redis, PHONE)
        sent = await deliver(known, monkeypatch)
    assert len(unknown.tasks) == 0 and len(known.tasks) == 1
    [(to, body)] = sent
    assert to == PHONE and "code is" in body
    code = body.split("code is ")[1][:6]
    assert all(code not in str(entry) for entry in logs)


@pytest.mark.asyncio
async def test_code_requests_are_rate_limited(db):
    redis = FakeRedis()
    for _ in range(settings.OTP_REQUESTS_PER_WINDOW):
        await request_code(db, redis, PHONE)
    with pytest.raises(OTPRateLimitedError):
        await request_code(db, redis, PHONE)


@pytest.mark.asyncio
async def test_login_code_signs_in_and_reset_code_gives_a_working_reset_token(db, request_, monkeypatch):
    redis = FakeRedis()
    sent = await deliver(await request_code(db, redis, PHONE, "login"), monkeypatch)
    code = sent[0][1].split("code is ")[1][:6]

    with pytest.raises(OTPInvalidError):
        await verify_otp(OTPVerify(phone_or_email=PHONE, code="000000" if code != "000000" else "111111", purpose="login"), request_, db=db)
    signed_in = await verify_otp(OTPVerify(phone_or_email=PHONE, code=code, purpose="login"), request_, db=db)
    assert signed_in.access_token and signed_in.refresh_token
    with pytest.raises(OTPInvalidError):  # a code works once
        await verify_otp(OTPVerify(phone_or_email=PHONE, code=code, purpose="login"), request_, db=db)

    sent = await deliver(await request_code(db, redis, PHONE, "password_reset"), monkeypatch)
    code = sent[0][1].split("code is ")[1][:6]
    reset = await verify_otp(OTPVerify(phone_or_email=PHONE, code=code, purpose="password_reset"), request_, db=db)
    assert reset.reset_token and reset.access_token is None
    assert await service.reset_password(db, reset.reset_token, "BrandNew9") is True
    assert await service.login(db, FakeRedis(), UserLogin(phone=PHONE, password="BrandNew9"), request_)
