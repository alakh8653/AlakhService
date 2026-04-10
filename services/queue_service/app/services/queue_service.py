import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.queue import Queue, QueueEntry
from app.schemas.queue import QueueCreate, QueueJoinRequest, QueuePositionResponse
from app.core.priority_queue import WeightedFairQueue
from app.core.exceptions import QueueNotFoundError, QueueFullError, EntryNotFoundError

log = structlog.get_logger()

# In-memory priority queues per queue_id
_pq_map: dict[str, WeightedFairQueue] = {}


class QueueService:

    def _get_pq(self, queue_id: str) -> WeightedFairQueue:
        if queue_id not in _pq_map:
            _pq_map[queue_id] = WeightedFairQueue()
        return _pq_map[queue_id]

    async def create_queue(self, db: AsyncSession, data: QueueCreate) -> Queue:
        q = Queue(
            id=str(uuid.uuid4()),
            service_id=data.service_id,
            max_capacity=data.max_capacity,
            current_size=0,
            is_accepting=True,
        )
        db.add(q)
        await db.flush()
        log.info("queue_created", queue_id=q.id, service_id=q.service_id)
        return q

    async def get_queue(self, db: AsyncSession, queue_id: str) -> Queue:
        result = await db.execute(select(Queue).where(Queue.id == queue_id))
        q = result.scalar_one_or_none()
        if not q:
            raise QueueNotFoundError()
        return q

    async def join_queue(self, db: AsyncSession, queue_id: str, data: QueueJoinRequest) -> QueueEntry:
        q = await self.get_queue(db, queue_id)
        if not q.is_accepting:
            raise QueueFullError("Queue is not accepting new entries")
        if q.current_size >= q.max_capacity:
            raise QueueFullError()

        pq = self._get_pq(queue_id)
        entry_id = str(uuid.uuid4())
        vft = pq.enqueue(entry_id, data.customer_id, data.weight, data.priority)

        position = pq.size()
        wait_minutes = position * 5  # rough estimate

        entry = QueueEntry(
            id=entry_id,
            queue_id=queue_id,
            customer_id=data.customer_id,
            service_id=data.service_id,
            priority=data.priority,
            weight=data.weight,
            position=position,
            status="WAITING",
            entered_at=datetime.now(timezone.utc),
            estimated_wait_minutes=wait_minutes,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
        )
        db.add(entry)
        q.current_size += 1
        await db.flush()
        log.info("queue_joined", queue_id=queue_id, customer_id=data.customer_id, position=position)
        return entry

    async def leave_queue(self, db: AsyncSession, queue_id: str, entry_id: str) -> None:
        result = await db.execute(
            select(QueueEntry).where(QueueEntry.id == entry_id, QueueEntry.queue_id == queue_id)
        )
        entry = result.scalar_one_or_none()
        if not entry:
            raise EntryNotFoundError()

        pq = self._get_pq(queue_id)
        pq.remove(entry_id)

        entry.status = "LEFT"
        result2 = await db.execute(select(Queue).where(Queue.id == queue_id))
        q = result2.scalar_one_or_none()
        if q and q.current_size > 0:
            q.current_size -= 1
        await db.flush()
        log.info("queue_left", queue_id=queue_id, entry_id=entry_id)

    async def get_position(self, db: AsyncSession, queue_id: str, customer_id: str) -> QueuePositionResponse:
        result = await db.execute(
            select(QueueEntry).where(
                QueueEntry.queue_id == queue_id,
                QueueEntry.customer_id == customer_id,
                QueueEntry.status == "WAITING",
            )
        )
        entry = result.scalar_one_or_none()
        if not entry:
            raise EntryNotFoundError("Customer not in queue")

        return QueuePositionResponse(
            customer_id=customer_id,
            queue_id=queue_id,
            position=entry.position,
            estimated_wait_minutes=entry.estimated_wait_minutes,
        )


queue_service = QueueService()
