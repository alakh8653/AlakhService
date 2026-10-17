import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import structlog
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import EntryNotFoundError, QueueFullError, QueueNotFoundError
from app.models.queue import Queue, QueueEntry
from app.schemas.queue import QueueCreate, QueueJoinRequest, QueuePositionResponse, QueueUpdate

log = structlog.get_logger()

# How much one finished service moves the queue's average (exponential moving average):
# recent customers count most, but one unusually long or short visit does not swing it.
LEARNING_RATE = 0.3
# Service times outside this range (a forgotten "done" tap, a mis-tap) are not learned from.
MIN_LEARNED_MINUTES, MAX_LEARNED_MINUTES = 1.0, 240.0


def _utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Timestamps read back from SQLite are naive; they are stored in UTC."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


@dataclass
class SoonNotice:
    """A customer to tell that their turn is near."""

    customer_id: str
    people_ahead: int
    estimated_wait_minutes: int


class QueueService:
    async def create_queue(self, db: AsyncSession, data: QueueCreate) -> Queue:
        q = Queue(
            id=str(uuid.uuid4()),
            service_id=data.service_id,
            max_capacity=data.max_capacity,
            current_size=0,
            is_accepting=True,
            servers=data.servers,
            avg_service_minutes=data.avg_service_minutes,
            no_show_grace_minutes=data.no_show_grace_minutes,
            notify_ahead=data.notify_ahead,
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

    async def get_queue(self, db: AsyncSession, queue_id: str, lock: bool = False) -> Queue:
        """The queue; with `lock`, its row stays locked until the transaction ends, so changes to the
        line (joining, leaving, calling the next customer) happen one at a time per queue."""
        stmt = select(Queue).where(Queue.id == queue_id)
        if lock:
            # Re-read after waiting for the lock: another request may have changed the queue meanwhile.
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        result = await db.execute(stmt)
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
            .execution_options(populate_existing=True)
        )
        return list(result.scalars().all())

    async def _in_service(self, db: AsyncSession, queue_id: str) -> int:
        """Customers called and not yet done or skipped: each one is keeping a server busy."""
        result = await db.execute(
            select(func.count()).where(QueueEntry.queue_id == queue_id, QueueEntry.status == "CALLED")
        )
        return result.scalar_one()

    @staticmethod
    def wait_minutes(q: Queue, people_ahead: int, in_service: int) -> int:
        """Minutes until this customer is called.

        With `servers` customers served at a time, everyone ahead and everyone already being served
        has to clear in rounds of `servers`, each round taking the queue's average service time.
        It assumes the people being served have just started, so it errs towards calling a
        customer a little earlier than promised rather than later.
        """
        servers = max(q.servers or 1, 1)
        busy = min(in_service, servers)
        return round(((people_ahead + busy) // servers) * (q.avg_service_minutes or 5.0))

    def _place(self, q: Queue, entry: QueueEntry, waiting: List[QueueEntry], in_service: int) -> QueueEntry:
        """Sets the entry's live position and wait estimate from the current waiting list."""
        ahead = next(i for i, e in enumerate(waiting) if e.id == entry.id)
        entry.position = ahead + 1
        entry.estimated_wait_minutes = self.wait_minutes(q, ahead, in_service)
        return entry

    async def _held_place(self, db: AsyncSession, q: Queue, customer_id: str) -> Optional[QueueEntry]:
        """The customer's current entry in the queue (waiting, or called and being served), if any."""
        waiting = await self._waiting(db, q.id)
        mine = next((e for e in waiting if e.customer_id == customer_id), None)
        if mine is not None:
            return self._place(q, mine, waiting, await self._in_service(db, q.id))
        return next((e for e in await self._called(db, q.id) if e.customer_id == customer_id), None)

    async def join_queue(self, db: AsyncSession, queue_id: str, data: QueueJoinRequest) -> QueueEntry:
        q = await self.get_queue(db, queue_id, lock=True)
        # Joining again (e.g. a retried tap) returns the place already held.
        mine = await self._held_place(db, q, data.customer_id)
        if mine is not None:
            return mine
        waiting = await self._waiting(db, queue_id)
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
        try:
            async with db.begin_nested():
                db.add(entry)
                q.current_size = len(waiting) + 1
        except IntegrityError:
            # The one-open-entry-per-customer index caught a join that did not go through the lock.
            mine = await self._held_place(db, await self.get_queue(db, queue_id, lock=True), data.customer_id)
            if mine is None:
                raise
            return mine
        self._place(q, entry, await self._waiting(db, queue_id), await self._in_service(db, queue_id))
        # Someone who joins already near the front can see that; no "almost your turn" notice.
        entry.notified_soon = entry.position - 1 < q.notify_ahead
        log.info("queue_joined", queue_id=queue_id, customer_id=data.customer_id, position=entry.position)
        return entry

    async def leave_queue(self, db: AsyncSession, queue_id: str, entry_id: str) -> None:
        await self.get_queue(db, queue_id, lock=True)
        result = await db.execute(
            select(QueueEntry)
            .where(QueueEntry.id == entry_id, QueueEntry.queue_id == queue_id)
            .execution_options(populate_existing=True)
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
        q = await self.get_queue(db, queue_id)
        now = datetime.now(timezone.utc)
        waiting = await self._waiting(db, queue_id)
        entry = next((e for e in waiting if e.customer_id == customer_id), None)
        if entry is None:
            # Called but not yet served: tell them it is their turn rather than "not in queue".
            called = (
                (
                    await db.execute(
                        select(QueueEntry)
                        .where(
                            QueueEntry.queue_id == queue_id,
                            QueueEntry.customer_id == customer_id,
                            QueueEntry.status == "CALLED",
                        )
                        .order_by(QueueEntry.called_at.desc())
                    )
                )
                .scalars()
                .first()
            )
            if called is None:
                raise EntryNotFoundError("Customer not in queue")
            return QueuePositionResponse(
                customer_id=customer_id,
                queue_id=queue_id,
                entry_id=called.id,
                status="CALLED",
                position=0,
                people_ahead=0,
                estimated_wait_minutes=0,
                estimated_call_at=_utc(called.called_at),
            )
        self._place(q, entry, waiting, await self._in_service(db, queue_id))
        return QueuePositionResponse(
            customer_id=customer_id,
            queue_id=queue_id,
            entry_id=entry.id,
            status="WAITING",
            position=entry.position,
            people_ahead=entry.position - 1,
            estimated_wait_minutes=entry.estimated_wait_minutes,
            estimated_call_at=now + timedelta(minutes=entry.estimated_wait_minutes),
        )

    async def waiting_list(self, db: AsyncSession, queue_id: str) -> List[QueueEntry]:
        """Who the shop is serving (called) followed by who is waiting, in serving order."""
        q = await self.get_queue(db, queue_id)
        waiting = await self._waiting(db, queue_id)
        called = await self._called(db, queue_id)
        in_service = len(called)
        return called + [self._place(q, e, waiting, in_service) for e in waiting]

    async def _called(self, db: AsyncSession, queue_id: str) -> List[QueueEntry]:
        result = await db.execute(
            select(QueueEntry)
            .where(QueueEntry.queue_id == queue_id, QueueEntry.status == "CALLED")
            .order_by(QueueEntry.called_at, QueueEntry.id)
            .execution_options(populate_existing=True)
        )
        return list(result.scalars().all())

    async def _skip_no_shows(self, db: AsyncSession, q: Queue, now: datetime) -> List[QueueEntry]:
        """Marks called customers who never turned up within the grace period as no-shows."""
        late = [
            e
            for e in await self._called(db, q.id)
            if _utc(e.called_at) is not None and now - _utc(e.called_at) > timedelta(minutes=q.no_show_grace_minutes)
        ]
        for e in late:
            e.status = "NO_SHOW"
            e.finished_at = now
        if late:
            log.info("queue_no_shows", queue_id=q.id, count=len(late))
        return late

    async def soon_notices(self, db: AsyncSession, queue_id: str) -> List[SoonNotice]:
        """Customers who are now near the front and have not been told yet; marks them told."""
        q = await self.get_queue(db, queue_id)
        if q.notify_ahead <= 0:
            return []
        waiting = await self._waiting(db, queue_id)
        in_service = await self._in_service(db, queue_id)
        notices = []
        for ahead, e in enumerate(waiting[: q.notify_ahead]):
            if not e.notified_soon:
                e.notified_soon = True
                notices.append(SoonNotice(e.customer_id, ahead, max(1, self.wait_minutes(q, ahead, in_service))))
        await db.flush()
        return notices

    async def call_next(self, db: AsyncSession, queue_id: str) -> Optional[QueueEntry]:
        """Takes the first waiting customer off the queue (they are being served), or None if it is empty.

        Called customers who never turned up within the queue's grace period are skipped as no-shows
        first, so they stop counting as being served.
        """
        # Locked so two "next" taps at once call two different customers, not the same one twice.
        q = await self.get_queue(db, queue_id, lock=True)
        now = datetime.now(timezone.utc)
        await self._skip_no_shows(db, q, now)
        waiting = await self._waiting(db, queue_id)
        if not waiting:
            await db.flush()
            return None
        head = waiting[0]
        head.status = "CALLED"
        head.position = 0
        head.estimated_wait_minutes = 0
        head.called_at = now
        await self._resize(db, queue_id)
        log.info("queue_called", queue_id=queue_id, entry_id=head.id)
        return head

    async def _called_entry(self, db: AsyncSession, queue_id: str, entry_id: str) -> QueueEntry:
        result = await db.execute(
            select(QueueEntry)
            .where(QueueEntry.id == entry_id, QueueEntry.queue_id == queue_id)
            .execution_options(populate_existing=True)
        )
        entry = result.scalar_one_or_none()
        if entry is None or entry.status != "CALLED":
            raise EntryNotFoundError("No called customer with this entry")
        return entry

    async def complete(self, db: AsyncSession, queue_id: str, entry_id: str) -> QueueEntry:
        """The shop has finished serving a called customer; the queue learns how long it took."""
        q = await self.get_queue(db, queue_id, lock=True)
        entry = await self._called_entry(db, queue_id, entry_id)
        now = datetime.now(timezone.utc)
        entry.status = "SERVED"
        entry.finished_at = now
        minutes = (now - _utc(entry.called_at)).total_seconds() / 60 if entry.called_at else None
        if minutes is not None and MIN_LEARNED_MINUTES <= minutes <= MAX_LEARNED_MINUTES:
            q.avg_service_minutes = round((1 - LEARNING_RATE) * q.avg_service_minutes + LEARNING_RATE * minutes, 2)
        await db.flush()
        log.info("queue_served", queue_id=queue_id, entry_id=entry_id, minutes=minutes, avg=q.avg_service_minutes)
        return entry

    async def no_show(self, db: AsyncSession, queue_id: str, entry_id: str) -> QueueEntry:
        """The shop marks a called customer who did not turn up, freeing their place for the next."""
        await self.get_queue(db, queue_id, lock=True)
        entry = await self._called_entry(db, queue_id, entry_id)
        entry.status = "NO_SHOW"
        entry.finished_at = datetime.now(timezone.utc)
        await db.flush()
        return entry

    async def update_settings(self, db: AsyncSession, queue_id: str, data: QueueUpdate) -> Queue:
        q = await self.get_queue(db, queue_id, lock=True)
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(q, field, value)
        await db.flush()
        return q

    async def set_accepting(self, db: AsyncSession, queue_id: str, accepting: bool) -> Queue:
        return await self.update_settings(db, queue_id, QueueUpdate(is_accepting=accepting))


queue_service = QueueService()
