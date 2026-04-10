import pytest
import pytest_asyncio
import os
import sys
import time

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.database import Base
from app.services.queue_service import QueueService
from app.schemas.queue import QueueCreate, QueueJoinRequest
from app.core.priority_queue import WeightedFairQueue
from app.core.exceptions import QueueNotFoundError, QueueFullError, EntryNotFoundError

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
    return QueueService()


@pytest.mark.anyio
async def test_enqueue_dequeue_order():
    pq = WeightedFairQueue()
    pq.enqueue("e1", "c1", weight=1.0, base_priority=0)
    time.sleep(0.001)
    pq.enqueue("e2", "c2", weight=1.0, base_priority=0)
    time.sleep(0.001)
    pq.enqueue("e3", "c3", weight=1.0, base_priority=0)
    # First dequeued should be e1 (lowest VFT = earliest)
    result = pq.dequeue()
    assert result[0] == "e1"
    result2 = pq.dequeue()
    assert result2[0] == "e2"


@pytest.mark.anyio
async def test_weighted_priority():
    pq = WeightedFairQueue()
    # High weight customer gets lower VFT (higher priority)
    pq.enqueue("e1", "low_weight_customer", weight=0.5, base_priority=0)
    pq.enqueue("e2", "high_weight_customer", weight=10.0, base_priority=0)
    # High weight should give lower VFT (1/weight is smaller for larger weight)
    first = pq.dequeue()
    assert first[0] == "e2"  # high weight goes first


@pytest.mark.anyio
async def test_queue_size():
    pq = WeightedFairQueue()
    assert pq.size() == 0
    pq.enqueue("e1", "c1")
    pq.enqueue("e2", "c2")
    assert pq.size() == 2
    pq.dequeue()
    assert pq.size() == 1


@pytest.mark.anyio
async def test_create_queue(db_session, service):
    q = await service.create_queue(db_session, QueueCreate(service_id="svc-1", max_capacity=10))
    assert q.id is not None
    assert q.service_id == "svc-1"
    assert q.current_size == 0
    assert q.is_accepting is True


@pytest.mark.anyio
async def test_join_queue(db_session, service):
    q = await service.create_queue(db_session, QueueCreate(service_id="svc-1"))
    entry = await service.join_queue(db_session, q.id, QueueJoinRequest(customer_id="cust-1", service_id="svc-1"))
    assert entry.customer_id == "cust-1"
    assert entry.status == "WAITING"


@pytest.mark.anyio
async def test_queue_full_error(db_session, service):
    q = await service.create_queue(db_session, QueueCreate(service_id="svc-1", max_capacity=1))
    await service.join_queue(db_session, q.id, QueueJoinRequest(customer_id="cust-1", service_id="svc-1"))
    with pytest.raises(QueueFullError):
        await service.join_queue(db_session, q.id, QueueJoinRequest(customer_id="cust-2", service_id="svc-1"))


@pytest.mark.anyio
async def test_queue_position(db_session, service):
    q = await service.create_queue(db_session, QueueCreate(service_id="svc-2"))
    await service.join_queue(db_session, q.id, QueueJoinRequest(customer_id="cust-1", service_id="svc-2"))
    await service.join_queue(db_session, q.id, QueueJoinRequest(customer_id="cust-2", service_id="svc-2"))
    pos = await service.get_position(db_session, q.id, "cust-2")
    assert pos.customer_id == "cust-2"
    assert pos.queue_id == q.id
