"""What payment_service and dispute_service tell booking_service (X-Internal-Key, never via the gateway)."""

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import payments
from app.core.fsm import BookingStatus
from app.core.internal import require_internal
from app.core.notifier import Notifier, get_notifier, notify_booking, snapshot
from app.core.payments import PaymentClient, get_payment_client, get_session_factory
from app.database import get_db
from app.dependencies import get_shop_owner_lookup
from app.routers.bookings import manager
from app.schemas.booking import DisputeResolution, PaymentStatusUpdate
from app.services.booking_service import booking_service

router = APIRouter(prefix="/internal/bookings", dependencies=[Depends(require_internal)])
log = structlog.get_logger()

SYSTEM = "system"


async def _booking(db: AsyncSession, booking_id: str):
    booking = await booking_service.get_booking(db, booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking


@router.post("/{booking_id}/payment-status")
async def set_payment_status(booking_id: str, body: PaymentStatusUpdate, db: AsyncSession = Depends(get_db)):
    """payment_service reports how the booking's payment stands; shown on the booking."""
    booking = await _booking(db, booking_id)
    if booking.payment_status != body.payment_status:
        booking.payment_status = body.payment_status
        await db.flush()
        log.info("booking_payment_status", booking_id=booking_id, payment_status=body.payment_status)
    return {"booking_id": booking.id, "payment_status": booking.payment_status}


@router.post("/{booking_id}/resolve-dispute")
async def resolve_dispute(
    booking_id: str,
    body: DisputeResolution,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    notifier: Notifier = Depends(get_notifier),
    lookup_owner=Depends(get_shop_owner_lookup),
    payment_client: PaymentClient = Depends(get_payment_client),
    session_factory=Depends(get_session_factory),
):
    """A dispute was resolved: the booking is COMPLETED again (the shop keeps the money) or REFUNDED.

    Repeating it is a no-op once the booking has that status, so dispute_service can retry.
    """
    booking = await _booking(db, booking_id)
    if booking.status == body.outcome:
        return {"booking_id": booking.id, "status": booking.status, "changed": False}
    if booking.status != BookingStatus.DISPUTED.value:
        raise HTTPException(status_code=409, detail=f"The booking is {booking.status}, not DISPUTED")
    booking = await booking_service.transition_status(
        db, booking_id, body.outcome, SYSTEM, f"Dispute resolved: {body.outcome.lower()}"
    )
    queued = await payments.enqueue(db, booking, payments.COMPLETED) if body.outcome == "COMPLETED" else None
    await manager.broadcast(booking_id, {"booking_id": booking_id, "status": booking.status})
    await db.commit()
    if queued is not None:
        background.add_task(payments.deliver_now, session_factory, payment_client, queued.id)
    if body.outcome == BookingStatus.REFUNDED.value:
        background.add_task(
            notify_booking,
            notifier,
            snapshot(booking),
            "booking.refunded",
            None,
            lookup_owner,
            roles=("customer", "shop"),
        )
    return {"booking_id": booking.id, "status": booking.status, "changed": True}
