import pytest
import pytest_asyncio
import os
import sys

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.database import Base
from app.services.admin_service import AdminService
from app.schemas.admin import AdminUserCreate, BanUserRequest, SystemConfigUpdate, BulkUpdateRequest

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
    return AdminService()


@pytest.mark.anyio
async def test_create_admin_user(db_session, service):
    admin = await service.create_admin_user(db_session, AdminUserCreate(user_id="u1", role="superadmin", permissions=["ban_user", "view_logs"]))
    assert admin.user_id == "u1"
    assert admin.role == "superadmin"
    assert admin.is_active is True


@pytest.mark.anyio
async def test_ban_user(db_session, service):
    result = await service.ban_user(db_session, "user-to-ban", BanUserRequest(reason="Fraud", banned_by="admin-1"))
    assert result["status"] == "banned"
    assert result["user_id"] == "user-to-ban"


@pytest.mark.anyio
async def test_unban_user(db_session, service):
    await service.ban_user(db_session, "user-2", BanUserRequest(reason="Test", banned_by="admin-1"))
    result = await service.unban_user(db_session, "user-2", "admin-1")
    assert result["status"] == "unbanned"


@pytest.mark.anyio
async def test_audit_log_creation(db_session, service):
    await service.ban_user(db_session, "user-3", BanUserRequest(reason="Spam", banned_by="admin-1"))
    logs = await service.get_audit_logs(db_session)
    assert len(logs) >= 1
    assert any(log.action == "ban_user" for log in logs)


@pytest.mark.anyio
async def test_system_config_update(db_session, service):
    config = await service.update_system_config(db_session, "max_bookings_per_day", SystemConfigUpdate(value="100", description="Max bookings", updated_by="admin-1"))
    assert config.key == "max_bookings_per_day"
    assert config.value == "100"
    
    # Update again
    config2 = await service.update_system_config(db_session, "max_bookings_per_day", SystemConfigUpdate(value="200", updated_by="admin-2"))
    assert config2.value == "200"


@pytest.mark.anyio
async def test_bulk_ban(db_session, service):
    result = await service.bulk_update(db_session, BulkUpdateRequest(user_ids=["u1", "u2", "u3"], action="ban", admin_id="admin-1", reason="Bulk test"))
    assert result["processed"] == 3
