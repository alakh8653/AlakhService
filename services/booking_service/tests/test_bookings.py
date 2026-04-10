import pytest
import pytest_asyncio
import os
import sys
from datetime import datetime, timezone, timedelta

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/2"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.database import Base
from app.models.booking import Booking, BookingStatusHistory, BookingAssignment
from app.services.booking_service import BookingService
from app.schemas.booking import BookingCreate
from app.core.fsm import BookingFSM, BookingStatus

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
    return BookingService()


def make_booking_create(**kwargs):
    defaults = {
        "customer_id": "cust-1",
        "service_id": "svc-1",
        "scheduled_at": datetime.now(timezone.utc) + timedelta(days=1),
        "duration_minutes": 60,
        "total_amount": 50000,
    }
    defaults.update(kwargs)
    return BookingCreate(**defaults)


@pytest.mark.anyio
async def test_create_booking(db_session, service):
    booking_data = make_booking_create()
    booking = await service.create_booking(db_session, "cust-1", booking_data)
    assert booking.status == "PENDING"
    assert booking.booking_number.startswith("BK")
    assert len(booking.booking_number) == 10  # BK + 8 digits


@pytest.mark.anyio
async def test_valid_fsm_transition_pending_to_confirmed(db_session, service):
    booking_data = make_booking_create()
    booking = await service.create_booking(db_session, "cust-1", booking_data)
    updated = await service.transition_status(db_session, booking.id, "CONFIRMED", "admin-1")
    assert updated.status == "CONFIRMED"


@pytest.mark.anyio
async def test_valid_fsm_transition_confirmed_to_assigned(db_session, service):
    booking_data = make_booking_create()
    booking = await service.create_booking(db_session, "cust-1", booking_data)
    await service.transition_status(db_session, booking.id, "CONFIRMED", "admin-1")
    updated = await service.transition_status(db_session, booking.id, "ASSIGNED", "provider-1")
    assert updated.status == "ASSIGNED"


@pytest.mark.anyio
async def test_invalid_fsm_transition_pending_to_completed(db_session, service):
    booking_data = make_booking_create()
    booking = await service.create_booking(db_session, "cust-1", booking_data)
    with pytest.raises(ValueError, match="Invalid transition"):
        await service.transition_status(db_session, booking.id, "COMPLETED", "admin-1")


@pytest.mark.anyio
async def test_invalid_fsm_transition_pending_to_in_progress(db_session, service):
    booking_data = make_booking_create()
    booking = await service.create_booking(db_session, "cust-1", booking_data)
    with pytest.raises(ValueError, match="Invalid transition"):
        await service.transition_status(db_session, booking.id, "IN_PROGRESS", "admin-1")


@pytest.mark.anyio
async def test_cancel_booking_from_pending(db_session, service):
    booking_data = make_booking_create()
    booking = await service.create_booking(db_session, "cust-1", booking_data)
    cancelled = await service.cancel_booking(db_session, booking.id, "cust-1", "Customer request")
    assert cancelled.status == "CANCELLED"
    assert cancelled.cancellation_reason == "Customer request"


@pytest.mark.anyio
async def test_cancel_booking_from_completed(db_session, service):
    booking_data = make_booking_create()
    booking = await service.create_booking(db_session, "cust-1", booking_data)
    await service.transition_status(db_session, booking.id, "CONFIRMED", "admin-1")
    await service.transition_status(db_session, booking.id, "ASSIGNED", "provider-1")
    await service.transition_status(db_session, booking.id, "PROVIDER_EN_ROUTE", "provider-1")
    await service.transition_status(db_session, booking.id, "IN_PROGRESS", "provider-1")
    await service.complete_booking(db_session, booking.id, "provider-1")
    with pytest.raises(ValueError, match="Invalid transition"):
        await service.cancel_booking(db_session, booking.id, "cust-1", "Too late")


@pytest.mark.anyio
async def test_booking_history_recorded(db_session, service):
    booking_data = make_booking_create()
    booking = await service.create_booking(db_session, "cust-1", booking_data)
    await service.transition_status(db_session, booking.id, "CONFIRMED", "admin-1")
    await service.transition_status(db_session, booking.id, "ASSIGNED", "provider-1")

    history = await service.get_booking_history(db_session, booking.id)
    assert len(history) == 3  # PENDING (created) + CONFIRMED + ASSIGNED
    assert history[0].to_status == "PENDING"
    assert history[1].to_status == "CONFIRMED"
    assert history[2].to_status == "ASSIGNED"


@pytest.mark.anyio
async def test_fsm_get_valid_transitions():
    fsm = BookingFSM()
    valid = fsm.get_valid_transitions(BookingStatus.PENDING)
    assert BookingStatus.CONFIRMED in valid
    assert BookingStatus.CANCELLED in valid
    assert BookingStatus.COMPLETED not in valid
    assert BookingStatus.IN_PROGRESS not in valid
