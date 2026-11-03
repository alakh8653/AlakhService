"""What other services tell booking_service (X-Internal-Key, never via the gateway)."""

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import payments, queue_hub
from app.core.fsm import BookingStatus
from app.core.internal import require_internal
from app.core.notifier import Notifier, get_notifier, notify_booking, snapshot
from app.core.payments import PaymentClient, get_payment_client, get_session_factory
from app.core.privacy import masked
from app.database import get_db
from app.dependencies import forget_shop_schedule, get_shop_owner_lookup
from app.models.booking import Booking
from app.routers.bookings import manager
from app.schemas.booking import DisputeResolution, PaymentStatusUpdate
from app.services.booking_service import booking_service

router = APIRouter(prefix="/internal/bookings", dependencies=[Depends(require_internal)])
log = structlog.get_logger()

SYSTEM = "system"

# When a shop is removed or rejected: these have not started, so they are cancelled and refunded...
NOT_STARTED = (BookingStatus.PENDING.value, BookingStatus.CONFIRMED.value, BookingStatus.ASSIGNED.value)
# ...and these are being served right now: an owner removing their shop has to finish them first, and
# after a rejection the shop still finishes them.
UNDER_WAY = (
    BookingStatus.PROVIDER_EN_ROUTE.value,
    BookingStatus.PICKED_UP.value,
    BookingStatus.IN_PROGRESS.value,
    BookingStatus.OUT_FOR_DELIVERY.value,
)
SHOP_REMOVED_REASON = "The shop is no longer on AlakhService"
# Not the admin's reason, which is about the shop's documents and is for its owner only.
SHOP_REJECTED_REASON = "The shop is not taking bookings right now"


async def _booking(db: AsyncSession, booking_id: str):
    booking = await booking_service.get_booking(db, booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking


@router.post("/{booking_id}/payment-status")
async def set_payment_status(
    booking_id: str, body: PaymentStatusUpdate, db: AsyncSession = Depends(get_db, scope="function")
):
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
    db: AsyncSession = Depends(get_db, scope="function"),
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


@router.post("/shops/{shop_id}/cancel-upcoming")
async def cancel_upcoming_for_removed_shop(
    shop_id: str,
    background: BackgroundTasks,
    because: str = Query("removed", pattern="^(removed|rejected)$"),
    db: AsyncSession = Depends(get_db, scope="function"),
    notifier: Notifier = Depends(get_notifier),
    lookup_owner=Depends(get_shop_owner_lookup),
    payment_client: PaymentClient = Depends(get_payment_client),
    session_factory=Depends(get_session_factory),
):
    """shop_service is removing or rejecting the shop: cancels what has not started, refunded in full as a
    cancellation by the shop, and tells the customers. A removal is refused, changing nothing, while a booking
    is being served; a rejection goes ahead and leaves that booking to finish.

    Repeating it finds nothing left to cancel, so shop_service can call it again.
    """
    rejected = because == "rejected"
    under_way = await db.scalar(
        select(func.count()).select_from(Booking).where(Booking.shop_id == shop_id, Booking.status.in_(UNDER_WAY))
    )
    if under_way and not rejected:
        raise HTTPException(status_code=409, detail=f"{under_way} booking(s) are being served: finish them first")
    ids = (
        await db.scalars(select(Booking.id).where(Booking.shop_id == shop_id, Booking.status.in_(NOT_STARTED)))
    ).all()
    cancelled = []
    for booking_id in ids:
        booking = await booking_service.cancel_booking(
            db, booking_id, SYSTEM, SHOP_REJECTED_REASON if rejected else SHOP_REMOVED_REASON
        )
        cancelled.append((booking, await payments.enqueue(db, booking, payments.CANCELLED, "shop")))
    await db.commit()
    forget_shop_schedule(shop_id)
    queue_hub.hub.poke(shop_id)
    for booking, queued in cancelled:
        await manager.broadcast(booking.id, {"booking_id": booking.id, "status": booking.status})
        background.add_task(payments.deliver_now, session_factory, payment_client, queued.id)
        background.add_task(
            notify_booking,
            notifier,
            snapshot(booking),
            "booking.cancelled",
            None,
            lookup_owner,
            roles=("customer", "provider"),
            extra={"reason": masked(booking.cancellation_reason)},
        )
    log.info("shop_closed_bookings_cancelled", shop_id=shop_id, because=because, count=len(cancelled))
    return {"shop_id": shop_id, "cancelled": len(cancelled), "under_way": under_way}
