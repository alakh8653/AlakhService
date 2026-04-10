import pytest
import pytest_asyncio
import os
import sys

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.database import Base
from app.services.compliance_service import ComplianceService, k_anonymity_check
from app.schemas.compliance import DataExportRequestCreate, DataErasureRequestCreate, ConsentRecordCreate
from app.core.exceptions import ExportRequestNotFoundError

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
    return ComplianceService()


@pytest.mark.anyio
async def test_consent_recording(db_session, service):
    record = await service.record_consent(db_session, ConsentRecordCreate(
        user_id="u1", consent_type="marketing_emails", granted=True,
        ip_address="192.168.1.1", user_agent="Mozilla/5.0"
    ))
    assert record.user_id == "u1"
    assert record.consent_type == "marketing_emails"
    assert record.granted is True


@pytest.mark.anyio
async def test_consent_versioning(db_session, service):
    await service.record_consent(db_session, ConsentRecordCreate(user_id="u1", consent_type="privacy_policy", granted=True, version="1.0"))
    await service.record_consent(db_session, ConsentRecordCreate(user_id="u1", consent_type="privacy_policy", granted=True, version="2.0"))
    consents = await service.get_user_consents(db_session, "u1")
    assert len(consents) == 2
    versions = [c.version for c in consents]
    assert "1.0" in versions
    assert "2.0" in versions


@pytest.mark.anyio
async def test_data_export_request(db_session, service):
    req = await service.initiate_export(db_session, DataExportRequestCreate(user_id="u1"))
    assert req.user_id == "u1"
    assert req.status == "PENDING"
    assert req.id is not None


@pytest.mark.anyio
async def test_data_export_completion(db_session, service):
    req = await service.initiate_export(db_session, DataExportRequestCreate(user_id="u1"))
    completed = await service.complete_export(db_session, req.id, "https://storage.example.com/exports/u1.zip")
    assert completed.status == "COMPLETED"
    assert completed.export_url is not None
    assert completed.completed_at is not None


@pytest.mark.anyio
async def test_erasure_request(db_session, service):
    req = await service.request_erasure(db_session, DataErasureRequestCreate(user_id="u2", reason="User requested deletion"))
    assert req.user_id == "u2"
    assert req.status == "PENDING"
    assert req.reason == "User requested deletion"


@pytest.mark.anyio
async def test_export_not_found(db_session, service):
    with pytest.raises(ExportRequestNotFoundError):
        await service.get_export_status(db_session, "nonexistent-id")


@pytest.mark.anyio
async def test_k_anonymity_check():
    assert k_anonymity_check(5, k=5) is True
    assert k_anonymity_check(10, k=5) is True
    assert k_anonymity_check(4, k=5) is False
    assert k_anonymity_check(1, k=5) is False


@pytest.mark.anyio
async def test_get_user_consents(db_session, service):
    await service.record_consent(db_session, ConsentRecordCreate(user_id="u3", consent_type="analytics", granted=False))
    await service.record_consent(db_session, ConsentRecordCreate(user_id="u3", consent_type="marketing", granted=True))
    consents = await service.get_user_consents(db_session, "u3")
    assert len(consents) == 2
