"""Telling payment_service about bookings that completed, were cancelled or were disputed.

The message is queued in payment_outbox in the booking change's own transaction, then delivered
right after the response and, if payment_service was down or refused it, retried by the worker with
growing delays. A cancel therefore always succeeds for the customer; the refund follows as soon as
payment_service can make it.
"""

import json
from datetime import datetime, timedelta, timezone
from typing import Callable, List, Optional

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.dependencies import path_segment
from app.models.booking import Booking, PaymentOutbox

log = structlog.get_logger()

COMPLETED, CANCELLED, DISPUTED = "completed", "cancelled", "disputed"
MAX_DELAY = timedelta(hours=1)
# After this many failed tries every retry is logged as an error, for someone to look at.
ALERT_AFTER_ATTEMPTS = 5


def _iso(at: Optional[datetime]) -> Optional[str]:
    if at is None:
        return None
    return (at if at.tzinfo else at.replace(tzinfo=timezone.utc)).isoformat()


def payload_for(kind: str, booking: Booking, now: datetime, cancelled_by: Optional[str] = None) -> dict:
    if kind == COMPLETED:
        return {
            "shop_id": booking.shop_id,
            "customer_id": booking.customer_id,  # earns loyalty points on it
            "total_amount": booking.total_amount,
            "completed_at": _iso(now),
        }
    if kind == CANCELLED:
        return {"cancelled_by": cancelled_by, "scheduled_at": _iso(booking.scheduled_at), "cancelled_at": _iso(now)}
    return {}


async def enqueue(
    db: AsyncSession, booking: Booking, kind: str, cancelled_by: Optional[str] = None
) -> Optional[PaymentOutbox]:
    """Queues [kind] for the booking, once: a booking is completed, cancelled or disputed at most once
    as far as payment_service is concerned (it settles each idempotently)."""
    existing = (
        await db.execute(
            select(PaymentOutbox).where(PaymentOutbox.booking_id == booking.id, PaymentOutbox.kind == kind)
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.delivered_at is not None and kind == COMPLETED:
            # Completed again after a dispute: send it again (payment_service ignores a repeat).
            existing.delivered_at = None
            existing.attempts = 0
            existing.next_attempt_at = datetime.now(timezone.utc)
            await db.flush()
        return existing
    now = datetime.now(timezone.utc)
    row = PaymentOutbox(
        booking_id=booking.id,
        kind=kind,
        payload=json.dumps(payload_for(kind, booking, now, cancelled_by)),
        attempts=0,
        next_attempt_at=now,
        created_at=now,
    )
    db.add(row)
    await db.flush()
    return row


class PaymentClient:
    """POSTs to payment_service's /internal/payments routes. Returns None on success, else why it failed."""

    def __init__(self, base_url: str, key: str, transport: Optional[httpx.AsyncBaseTransport] = None):
        self.base_url = base_url
        self.key = key
        self._transport = transport

    @property
    def configured(self) -> bool:
        return bool(self.key)

    async def send(self, booking_id: str, kind: str, payload: dict) -> Optional[str]:
        if not self.key:
            return "INTERNAL_API_KEY is not set"
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=10.0, transport=self._transport) as client:
                resp = await client.post(
                    f"/internal/payments/booking/{path_segment(booking_id)}/{kind}",
                    json=payload,
                    headers={"X-Internal-Key": self.key},
                )
        except httpx.HTTPError as e:
            return f"unreachable: {e}"
        if resp.status_code >= 400:
            return f"{resp.status_code}: {resp.text[:200]}"
        return None


def get_payment_client() -> PaymentClient:
    return PaymentClient(settings.PAYMENT_SERVICE_URL, settings.INTERNAL_API_KEY)


SessionFactory = Callable[[], AsyncSession]


def get_session_factory() -> async_sessionmaker:
    from app.database import AsyncSessionLocal

    return AsyncSessionLocal


def _locked(query, db: AsyncSession):
    # Several replicas run the worker: each row is taken by one of them (PostgreSQL); SQLite has one writer.
    if db.get_bind().dialect.name == "postgresql":
        return query.with_for_update(skip_locked=True)
    return query


async def _attempt(db: AsyncSession, row: PaymentOutbox, client: PaymentClient, now: datetime) -> bool:
    error = await client.send(row.booking_id, row.kind, json.loads(row.payload))
    row.attempts += 1
    if error is None:
        row.delivered_at = now
        row.last_error = None
        log.info("payment_sync_delivered", booking_id=row.booking_id, kind=row.kind, attempts=row.attempts)
        return True
    row.last_error = error
    row.next_attempt_at = now + min(timedelta(seconds=30 * 2 ** (row.attempts - 1)), MAX_DELAY)
    level = log.error if row.attempts >= ALERT_AFTER_ATTEMPTS else log.warning
    level("payment_sync_failed", booking_id=row.booking_id, kind=row.kind, attempts=row.attempts, error=error)
    return False


async def deliver_now(factory: SessionFactory, client: PaymentClient, outbox_id: str) -> None:
    """Delivers one queued message right after the booking change (best effort; the worker retries)."""
    if not client.configured:
        return
    try:
        async with factory() as db:
            row = (
                await db.execute(
                    _locked(
                        select(PaymentOutbox).where(
                            PaymentOutbox.id == outbox_id, PaymentOutbox.delivered_at.is_(None)
                        ),
                        db,
                    )
                )
            ).scalar_one_or_none()
            if row is None:
                return
            await _attempt(db, row, client, datetime.now(timezone.utc))
            await db.commit()
    except Exception as e:  # never surfaces to the person who cancelled
        log.warning("payment_sync_error", outbox_id=outbox_id, error=str(e))


async def deliver_due(db: AsyncSession, client: PaymentClient, now: datetime, limit: int = 50) -> List[PaymentOutbox]:
    """Retries queued messages whose time has come; returns those it tried. The caller commits."""
    if not client.configured:
        return []
    rows = (
        (
            await db.execute(
                _locked(
                    select(PaymentOutbox)
                    .where(PaymentOutbox.delivered_at.is_(None), PaymentOutbox.next_attempt_at <= now)
                    .order_by(PaymentOutbox.next_attempt_at)
                    .limit(limit),
                    db,
                )
            )
        )
        .scalars()
        .all()
    )
    for row in rows:
        await _attempt(db, row, client, now)
    return list(rows)
