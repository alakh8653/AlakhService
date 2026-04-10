import pytest
import pytest_asyncio
import os
import sys

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.database import Base
from app.services.dispute_service import DisputeService
from app.schemas.dispute import DisputeCreate, DisputeMessageCreate
from app.core.fsm import DisputeFSM, DisputeStatus
from app.core.exceptions import DisputeNotFoundError

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
    return DisputeService()


def make_dispute(**kwargs):
    defaults = {"booking_id": "b1", "raised_by": "u1", "dispute_type": "quality", "description": "Service was poor"}
    defaults.update(kwargs)
    return DisputeCreate(**defaults)


@pytest.mark.anyio
async def test_create_dispute(db_session, service):
    dispute = await service.create_dispute(db_session, make_dispute())
    assert dispute.id is not None
    assert dispute.status == "OPEN"
    assert dispute.booking_id == "b1"


@pytest.mark.anyio
async def test_fsm_open_to_under_review(db_session, service):
    dispute = await service.create_dispute(db_session, make_dispute())
    updated = await service.transition(db_session, dispute.id, "UNDER_REVIEW")
    assert updated.status == "UNDER_REVIEW"


@pytest.mark.anyio
async def test_fsm_invalid_transition(db_session, service):
    # OPEN -> ESCALATED is invalid (must go through UNDER_REVIEW first)
    dispute = await service.create_dispute(db_session, make_dispute(booking_id="b2"))
    with pytest.raises(ValueError):
        await service.transition(db_session, dispute.id, "ESCALATED")


@pytest.mark.anyio
async def test_fsm_under_review_to_escalated(db_session, service):
    dispute = await service.create_dispute(db_session, make_dispute(booking_id="b3"))
    await service.transition(db_session, dispute.id, "UNDER_REVIEW")
    updated = await service.transition(db_session, dispute.id, "ESCALATED")
    assert updated.status == "ESCALATED"


@pytest.mark.anyio
async def test_resolve_dispute(db_session, service):
    dispute = await service.create_dispute(db_session, make_dispute(booking_id="b4"))
    await service.transition(db_session, dispute.id, "UNDER_REVIEW")
    resolved = await service.resolve(db_session, dispute.id, "Refund issued")
    assert resolved.status == "RESOLVED"
    assert resolved.resolution == "Refund issued"
    assert resolved.resolved_at is not None


@pytest.mark.anyio
async def test_add_and_get_messages(db_session, service):
    dispute = await service.create_dispute(db_session, make_dispute(booking_id="b5"))
    await service.add_message(db_session, dispute.id, DisputeMessageCreate(author_id="u1", content="Hello"))
    await service.add_message(db_session, dispute.id, DisputeMessageCreate(author_id="admin-1", content="We are reviewing"))
    msgs = await service.get_messages(db_session, dispute.id)
    assert len(msgs) == 2
    assert msgs[0].content == "Hello"


@pytest.mark.anyio
async def test_dispute_not_found(db_session, service):
    with pytest.raises(DisputeNotFoundError):
        await service.get_dispute(db_session, "nonexistent")


@pytest.mark.anyio
async def test_fsm_transitions_list():
    fsm = DisputeFSM()
    assert DisputeStatus.UNDER_REVIEW in fsm.get_valid_transitions(DisputeStatus.OPEN)
    assert DisputeStatus.ESCALATED not in fsm.get_valid_transitions(DisputeStatus.OPEN)
    assert DisputeStatus.RESOLVED in fsm.get_valid_transitions(DisputeStatus.ESCALATED)
