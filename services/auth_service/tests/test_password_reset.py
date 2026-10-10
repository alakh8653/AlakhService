"""Password reset tokens: single purpose, single use, never logged; only access tokens authenticate."""
import os
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from structlog.testing import capture_logs

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from app.core.exceptions import InvalidCredentialsError, InvalidTokenError  # noqa: E402
from app.core.security import create_access_token, create_password_reset_token  # noqa: E402
from app.database import Base  # noqa: E402
from app.dependencies import get_current_user  # noqa: E402
from app.models.user import RefreshToken, User  # noqa: E402
from app.routers.auth import forgot_password  # noqa: E402
from app.schemas.auth import PasswordResetRequest, UserCreate, UserLogin  # noqa: E402
from app.services.auth_service import AuthService  # noqa: E402

service = AuthService()


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)() as session:
        yield session
    await engine.dispose()


@pytest.fixture
def redis():
    r = AsyncMock()
    r.get = AsyncMock(return_value=None)
    r.ttl = AsyncMock(return_value=-1)
    return r


@pytest.fixture
def request_():
    req = MagicMock()
    req.client.host = "127.0.0.1"
    req.headers = {"user-agent": "test-agent"}
    return req


async def signed_up(db, redis, request_):
    user = await service.register(db, UserCreate(email="reset@example.com", password="Password1", full_name="Reset User"))
    tokens = await service.login(db, redis, UserLogin(email="reset@example.com", password="Password1"), request_)
    return user, tokens


async def authenticate(token: str):
    return await get_current_user(HTTPAuthorizationCredentials(scheme="Bearer", credentials=token), db=None)


@pytest.mark.asyncio
async def test_login_tokens_cannot_reset_a_password(db, redis, request_):
    user, tokens = await signed_up(db, redis, request_)
    for token in (tokens.access_token, tokens.refresh_token):
        with pytest.raises(InvalidTokenError):
            await service.reset_password(db, token, "NewPassword1")
    # The old purpose-tagged access token format is rejected too.
    legacy = create_access_token({"sub": str(user.id), "purpose": "password_reset"})
    with pytest.raises(InvalidTokenError):
        await service.reset_password(db, legacy, "NewPassword1")


@pytest.mark.asyncio
async def test_reset_token_works_once_and_signs_out_other_sessions(db, redis, request_):
    user, _ = await signed_up(db, redis, request_)
    token = create_password_reset_token(str(user.id), user.hashed_password)

    assert await service.reset_password(db, token, "NewPassword1") is True
    with pytest.raises(InvalidTokenError):
        await service.reset_password(db, token, "Another1")

    open_sessions = await db.execute(
        select(RefreshToken).where(RefreshToken.user_id == str(user.id), RefreshToken.is_revoked == False)  # noqa: E712
    )
    assert open_sessions.scalars().all() == []

    with pytest.raises(InvalidCredentialsError):
        await service.login(db, redis, UserLogin(email="reset@example.com", password="Password1"), request_)
    assert await service.login(db, redis, UserLogin(email="reset@example.com", password="NewPassword1"), request_)


@pytest.mark.asyncio
async def test_only_access_tokens_authenticate(db, redis, request_):
    user, tokens = await signed_up(db, redis, request_)
    assert (await authenticate(tokens.access_token))["sub"] == str(user.id)
    for token in (
        tokens.refresh_token,
        create_password_reset_token(str(user.id), user.hashed_password),
        create_access_token({"sub": str(user.id), "purpose": "password_reset"}),
    ):
        with pytest.raises(HTTPException) as exc:
            await authenticate(token)
        assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_forgot_password_does_not_log_the_token(db, redis, request_):
    await signed_up(db, redis, request_)
    with capture_logs() as logs:
        await forgot_password(PasswordResetRequest(email="reset@example.com"), db=db)
    assert [entry["event"] for entry in logs] == ["password_reset_requested"]
    assert all("token" not in entry for entry in logs)
    assert (await db.execute(select(User))).scalars().one()
