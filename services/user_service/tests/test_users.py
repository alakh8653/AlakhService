import pytest
import pytest_asyncio
import os
import sys

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/1"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.database import Base
from app.models.user import UserProfile, UserAddress, UserPreferences, UserDevice
from app.services.user_service import UserService
from app.schemas.user import (
    UserProfileCreate, UserAddressCreate, UserAddressUpdate,
    UserPreferencesUpdate, UserDeviceCreate,
)

pytest_plugins = ("anyio",)

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


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
def service():
    return UserService()


@pytest.mark.anyio
async def test_create_profile(db_session, service):
    profile_data = UserProfileCreate(full_name="John Doe", language="en", timezone="UTC")
    profile = await service.create_or_update_profile(db_session, "user-1", profile_data)
    assert profile.user_id == "user-1"
    assert profile.full_name == "John Doe"


@pytest.mark.anyio
async def test_update_profile(db_session, service):
    profile_data = UserProfileCreate(full_name="Jane Doe")
    await service.create_or_update_profile(db_session, "user-2", profile_data)

    update_data = UserProfileCreate(full_name="Jane Smith", bio="Hello World")
    updated = await service.create_or_update_profile(db_session, "user-2", update_data)
    assert updated.full_name == "Jane Smith"
    assert updated.bio == "Hello World"


@pytest.mark.anyio
async def test_add_address(db_session, service):
    address_data = UserAddressCreate(
        label="Home",
        street="123 Main St",
        city="Mumbai",
        state="Maharashtra",
        postal_code="400001",
        country="India",
    )
    address = await service.add_address(db_session, "user-3", address_data)
    assert address.city == "Mumbai"
    assert address.is_default is True  # First address should be default


@pytest.mark.anyio
async def test_second_address_not_default(db_session, service):
    addr1 = UserAddressCreate(
        label="Home", street="1 Main St", city="Delhi",
        state="Delhi", postal_code="110001", country="India",
    )
    addr2 = UserAddressCreate(
        label="Work", street="2 Business Ave", city="Delhi",
        state="Delhi", postal_code="110002", country="India",
    )
    await service.add_address(db_session, "user-4", addr1)
    second = await service.add_address(db_session, "user-4", addr2)
    assert second.is_default is False


@pytest.mark.anyio
async def test_set_default_address(db_session, service):
    addr1 = UserAddressCreate(
        label="Home", street="1 Main St", city="Delhi",
        state="Delhi", postal_code="110001", country="India",
    )
    addr2 = UserAddressCreate(
        label="Work", street="2 Business Ave", city="Delhi",
        state="Delhi", postal_code="110002", country="India",
    )
    first = await service.add_address(db_session, "user-5", addr1)
    second = await service.add_address(db_session, "user-5", addr2)

    success = await service.set_default_address(db_session, "user-5", second.id)
    assert success is True

    addresses = await service.get_addresses(db_session, "user-5")
    defaults = [a for a in addresses if a.is_default]
    assert len(defaults) == 1
    assert defaults[0].id == second.id


@pytest.mark.anyio
async def test_delete_address(db_session, service):
    address_data = UserAddressCreate(
        label="Temp", street="5 Temp St", city="Pune",
        state="Maharashtra", postal_code="411001", country="India",
    )
    address = await service.add_address(db_session, "user-6", address_data)
    deleted = await service.delete_address(db_session, "user-6", address.id)
    assert deleted is True

    addresses = await service.get_addresses(db_session, "user-6")
    assert len(addresses) == 0


@pytest.mark.anyio
async def test_get_preferences_creates_defaults(db_session, service):
    prefs = await service.get_preferences(db_session, "user-7")
    assert prefs.user_id == "user-7"
    assert prefs.currency == "INR"
    assert prefs.theme == "light"
    assert prefs.notifications_enabled is True


@pytest.mark.anyio
async def test_update_preferences(db_session, service):
    await service.get_preferences(db_session, "user-8")
    update_data = UserPreferencesUpdate(currency="USD", theme="dark")
    prefs = await service.update_preferences(db_session, "user-8", update_data)
    assert prefs.currency == "USD"
    assert prefs.theme == "dark"


@pytest.mark.anyio
async def test_register_device(db_session, service):
    device_data = UserDeviceCreate(
        device_token="token-abc",
        platform="android",
        device_id="device-001",
    )
    device = await service.register_device(db_session, "user-9", device_data)
    assert device.platform == "android"
    assert device.is_active is True
    assert device.device_id == "device-001"


@pytest.mark.anyio
async def test_deregister_device(db_session, service):
    device_data = UserDeviceCreate(
        device_token="token-xyz",
        platform="ios",
        device_id="device-002",
    )
    await service.register_device(db_session, "user-10", device_data)
    success = await service.deregister_device(db_session, "user-10", "device-002")
    assert success is True

    devices = await service.get_active_devices(db_session, "user-10")
    assert len(devices) == 0
