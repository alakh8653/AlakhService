import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import EntryNotFoundError, QueueFullError, QueueNotFoundError
from app.models.queue import Queue, QueueEntry
from app.schemas.queue import QueueCreate, QueueJoinRequest, QueuePositionResponse

log = structlog.get_logger()

# Rough service time per customer ahead, for the wait estimate.
MINUTES_PER_CUSTOMER = 5


class QueueService:

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

    async def queues_for_service(self, db: AsyncSession, service_id: str, include_closed: bool = False) -> List[Queue]:
        """Queues currently taking customers for a service (or every queue it has)."""
        stmt = select(Queue).where(Queue.service_id == service_id)
        if not include_closed:
            stmt = stmt.where(Queue.is_accepting.is_(True))
        result = await db.execute(stmt.order_by(Queue.created_at))
        return list(result.scalars().all())

    async def get_queue(self, db: AsyncSession, queue_id: str) -> Queue:
        result = await db.execute(select(Queue).where(Queue.id == queue_id))
        q = result.scalar_one_or_none()
        if not q:
            raise QueueNotFoundError()
        return q

    async def _waiting(self, db: AsyncSession, queue_id: str) -> List[QueueEntry]:
        """Customers still waiting, in serving order: higher priority first, then who came first."""
        result = await db.execute(
            select(QueueEntry)
            .where(QueueEntry.queue_id == queue_id, QueueEntry.status == "WAITING")
            .order_by(QueueEntry.priority.desc(), QueueEntry.entered_at, QueueEntry.id)
        )
        return list(result.scalars().all())

    def _place(self, entry: QueueEntry, waiting: List[QueueEntry]) -> QueueEntry:
        """Sets the entry's live position and wait estimate from the current waiting list."""
        ahead = next(i for i, e in enumerate(waiting) if e.id == entry.id)
        entry.position = ahead + 1
        entry.estimated_wait_minutes = ahead * MINUTES_PER_CUSTOMER
        return entry

    async def join_queue(self, db: AsyncSession, queue_id: str, data: QueueJoinRequest) -> QueueEntry:
        q = await self.get_queue(db, queue_id)
        waiting = await self._waiting(db, queue_id)
        # Joining again (e.g. a retried tap) returns the place already held.
        mine = next((e for e in waiting if e.customer_id == data.customer_id), None)
        if mine is not None:
            return self._place(mine, waiting)
        if not q.is_accepting:
            raise QueueFullError("Queue is not accepting new entries")
        if len(waiting) >= q.max_capacity:
            raise QueueFullError()

        now = datetime.now(timezone.utc)
        entry = QueueEntry(
            id=str(uuid.uuid4()),
            queue_id=queue_id,
            customer_id=data.customer_id,
            service_id=data.service_id,
            priority=data.priority,
            weight=data.weight,
            position=0,
            status="WAITING",
            entered_at=now,
            expires_at=now + timedelta(hours=2),
        )
        db.add(entry)
        q.current_size = len(waiting) + 1
        await db.flush()
        self._place(entry, await self._waiting(db, queue_id))
        log.info("queue_joined", queue_id=queue_id, customer_id=data.customer_id, position=entry.position)
        return entry

    async def leave_queue(self, db: AsyncSession, queue_id: str, entry_id: str) -> None:
        result = await db.execute(
            select(QueueEntry).where(QueueEntry.id == entry_id, QueueEntry.queue_id == queue_id)
        )
        entry = result.scalar_one_or_none()
        if not entry:
            raise EntryNotFoundError()
        if entry.status == "WAITING":
            entry.status = "LEFT"
            await self._resize(db, queue_id)
        log.info("queue_left", queue_id=queue_id, entry_id=entry_id)

    async def _resize(self, db: AsyncSession, queue_id: str) -> None:
        await db.flush()
        q = await self.get_queue(db, queue_id)
        q.current_size = len(await self._waiting(db, queue_id))
        await db.flush()

    async def get_position(self, db: AsyncSession, queue_id: str, customer_id: str) -> QueuePositionResponse:
        waiting = await self._waiting(db, queue_id)
        entry = next((e for e in waiting if e.customer_id == customer_id), None)
        if not entry:
            raise EntryNotFoundError("Customer not in queue")
        self._place(entry, waiting)
        return QueuePositionResponse(
            customer_id=customer_id,
            queue_id=queue_id,
            position=entry.position,
            estimated_wait_minutes=entry.estimated_wait_minutes,
        )

    async def waiting_list(self, db: AsyncSession, queue_id: str) -> List[QueueEntry]:
        await self.get_queue(db, queue_id)
        waiting = await self._waiting(db, queue_id)
        return [self._place(e, waiting) for e in waiting]

    async def call_next(self, db: AsyncSession, queue_id: str) -> Optional[QueueEntry]:
        """Takes the first waiting customer off the queue (they are being served), or None if it is empty."""
        waiting = await self._waiting(db, queue_id)
        if not waiting:
            return None
        head = waiting[0]
        head.status = "CALLED"
        head.position = 0
        head.estimated_wait_minutes = 0
        await self._resize(db, queue_id)
        log.info("queue_called", queue_id=queue_id, entry_id=head.id)
        return head

    async def set_accepting(self, db: AsyncSession, queue_id: str, accepting: bool) -> Queue:
        q = await self.get_queue(db, queue_id)
        q.is_accepting = accepting
        await db.flush()
        return q


queue_service = QueueService()
