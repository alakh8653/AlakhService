import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
import sys
import os

# Patch the DATABASE_URL before importing app modules
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

# We need to override the engine in database.py
# Instead, we create our own engine and session for tests

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Import app modules after setting env vars
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base
from app.models.user import User, RefreshToken, OTPCode, LoginAttempt
from app.services.auth_service import AuthService
from app.schemas.auth import UserCreate, UserLogin, OTPRequest, OTPVerify
from app.core.exceptions import (
    InvalidCredentialsError, UserAlreadyExistsError,
    AccountLockedError, InvalidTokenError,
)
from app.core.security import hash_token

pytest_plugins = ("anyio",)


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine):
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
def mock_redis():
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=True)
    redis.ttl = AsyncMock(return_value=-1)
    redis.setex = AsyncMock(return_value=True)
    return redis


@pytest_asyncio.fixture
def mock_request():
    request = MagicMock()
    request.client = MagicMock()
    request.client.host = "127.0.0.1"
    request.headers = {"user-agent": "test-agent"}
    return request


@pytest_asyncio.fixture
def service():
    return AuthService()


@pytest.mark.anyio
async def test_register_user(db_session, service):
    user_create = UserCreate(
        email="test@example.com",
        password="Password1",
        full_name="Test User",
    )
    user = await service.register(db_session, user_create)
    assert user.email == "test@example.com"
    assert user.role == "user"
    assert user.is_active is True
    assert user.is_verified is False


@pytest.mark.anyio
async def test_login_success(db_session, service, mock_redis, mock_request):
    user_create = UserCreate(
        email="login@example.com",
        password="Password1",
        full_name="Login User",
    )
    await service.register(db_session, user_create)

    login_data = UserLogin(email="login@example.com", password="Password1")
    token_response = await service.login(db_session, mock_redis, login_data, mock_request)
    assert token_response.access_token
    assert token_response.refresh_token
    assert token_response.token_type == "bearer"


@pytest.mark.anyio
async def test_login_wrong_password(db_session, service, mock_redis, mock_request):
    user_create = UserCreate(
        email="wrongpass@example.com",
        password="Password1",
        full_name="Wrong Pass User",
    )
    await service.register(db_session, user_create)

    login_data = UserLogin(email="wrongpass@example.com", password="WrongPass1")
    with pytest.raises(InvalidCredentialsError):
        await service.login(db_session, mock_redis, login_data, mock_request)


@pytest.mark.anyio
async def test_brute_force_lockout(db_session, service, mock_redis, mock_request):
    user_create = UserCreate(
        email="brute@example.com",
        password="Password1",
        full_name="Brute Force User",
    )
    await service.register(db_session, user_create)

    login_data = UserLogin(email="brute@example.com", password="WrongPass1")

    # Simulate redis returning 5 attempts (already at limit)
    mock_redis.get = AsyncMock(return_value=b"5")
    mock_redis.ttl = AsyncMock(return_value=300)

    with pytest.raises(AccountLockedError):
        await service.login(db_session, mock_redis, login_data, mock_request)


@pytest.mark.anyio
async def test_refresh_token_rotation(db_session, service, mock_redis, mock_request):
    user_create = UserCreate(
        email="refresh@example.com",
        password="Password1",
        full_name="Refresh User",
    )
    await service.register(db_session, user_create)

    login_data = UserLogin(email="refresh@example.com", password="Password1")
    tokens = await service.login(db_session, mock_redis, login_data, mock_request)

    new_tokens = await service.refresh_tokens(db_session, mock_redis, tokens.refresh_token, mock_request)
    assert new_tokens.access_token != tokens.access_token
    assert new_tokens.refresh_token != tokens.refresh_token


@pytest.mark.anyio
async def test_logout_invalidates_token(db_session, service, mock_redis, mock_request):
    from sqlalchemy import select as sa_select

    user_create = UserCreate(
        email="logout@example.com",
        password="Password1",
        full_name="Logout User",
    )
    user = await service.register(db_session, user_create)

    login_data = UserLogin(email="logout@example.com", password="Password1")
    tokens = await service.login(db_session, mock_redis, login_data, mock_request)

    await service.logout(db_session, mock_redis, str(user.id), tokens.refresh_token)

    # Check that the refresh token is revoked
    token_hash = hash_token(tokens.refresh_token)
    result = await db_session.execute(
        sa_select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    rt = result.scalar_one_or_none()
    assert rt is not None
    assert rt.is_revoked is True
