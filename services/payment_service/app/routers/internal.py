"""What booking_service and dispute_service tell payment_service about a booking's money.

Every call is idempotent, so the callers can retry until they get an answer:
- completed: record the shop's earning and the platform's commission, releasing the escrow;
- cancelled: refund as the cancellation policy says;
- disputed / release: hold the earning back from payouts while a dispute is open, and let it go;
- refund: a dispute resolved with a full or partial refund.
"""

from typing import Optional

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.internal import require_internal
from app.core.notifier import Notifier, get_notifier, notify_payment, payment_snapshot
from app.core.peers import BookingSync, get_booking_sync
from app.core.razorpay import GatewayError, RazorpayGateway, get_razorpay
from app.database import get_db
from app.models.payment import ShopEarning
from app.schemas.money import (
    BookingCancelled,
    BookingCompleted,
    DisputeRefund,
    DisputeRelease,
    LoyaltyRedeem,
    LoyaltyRelease,
)
from app.schemas.payment import RefundRequest
from app.services import earnings_service, loyalty_service
from app.services.payment_service import payment_service

router = APIRouter(prefix="/internal/payments", dependencies=[Depends(require_internal)])
log = structlog.get_logger()


def _earning(e: Optional[ShopEarning]) -> Optional[dict]:
    if e is None:
        return None
    return {
        "booking_id": e.booking_id,
        "shop_id": e.shop_id,
        "collection": e.collection,
        "gross_cents": e.gross_cents,
        "commission_cents": e.commission_cents,
        "gst_cents": e.gst_cents,
        "net_cents": e.net_cents,
        "payout_cents": e.payout_cents,
        "status": e.status,
    }


async def _announce_refund(
    db: AsyncSession, background: BackgroundTasks, notifier: Notifier, sync: BookingSync, refund, booking_id: str
) -> None:
    """After a refund: the payer is told, and booking_service learns the booking's payment status."""
    payment = await payment_service.get_payment(db, refund.payment_id)
    status = await payment_service.booking_payment_status(db, booking_id)
    await db.commit()  # visible before anyone is told
    background.add_task(
        notify_payment, notifier, "payment.refunded", {**payment_snapshot(payment), "amount_cents": refund.amount_cents}
    )
    background.add_task(sync.payment_status, booking_id, status)


@router.post("/booking/{booking_id}/completed")
async def booking_completed(booking_id: str, body: BookingCompleted, db: AsyncSession = Depends(get_db)):
    try:
        earning, created = await earnings_service.settle_booking(
            db, booking_id, body.shop_id, body.total_amount, body.completed_at
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    points = 0
    if body.customer_id and earning.status != "REFUNDED":
        # Points on what the customer paid themselves, not on what their points paid.
        points = await loyalty_service.booking_completed(
            db, booking_id, body.customer_id, earning.gross_cents - earning.platform_discount_cents
        )
    return {"created": created, "earning": _earning(earning), "points_earned": points}


@router.post("/loyalty/redeem")
async def redeem_points(body: LoyaltyRedeem, db: AsyncSession = Depends(get_db)):
    """Spends the customer's points on a booking being made; returns the discount (0 when they have none)."""
    discount = await loyalty_service.redeem(db, body.customer_id, body.booking_id, body.price_cents)
    return {"booking_id": body.booking_id, "discount_cents": discount}


@router.post("/loyalty/release")
async def release_points(body: LoyaltyRelease, db: AsyncSession = Depends(get_db)):
    """A booking the points were spent on was never made after all: they go back."""
    return {"booking_id": body.booking_id, "points_returned": await loyalty_service.return_points(db, body.booking_id)}


@router.post("/booking/{booking_id}/cancelled")
async def booking_cancelled(
    booking_id: str,
    body: BookingCancelled,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    gateway: RazorpayGateway = Depends(get_razorpay),
    notifier: Notifier = Depends(get_notifier),
    sync: BookingSync = Depends(get_booking_sync),
):
    try:
        result = await payment_service.booking_cancelled(
            db, booking_id, body.cancelled_by, body.scheduled_at, body.cancelled_at, gateway
        )
    except GatewayError as e:
        log.warning("cancel_refund_gateway_failed", booking_id=booking_id, error=str(e))
        raise HTTPException(status_code=502, detail="Razorpay could not process the refund") from e
    except ValueError as e:  # e.g. Razorpay is not configured: booking_service keeps it queued
        log.error("cancel_refund_failed", booking_id=booking_id, error=str(e))
        raise HTTPException(status_code=503, detail=str(e)) from e
    if result["status"] == "refunded":
        refund = await payment_service.get_refund(db, result["refund_id"])
        await _announce_refund(db, background, notifier, sync, refund, booking_id)
    return result


@router.post("/booking/{booking_id}/disputed")
async def booking_disputed(booking_id: str, db: AsyncSession = Depends(get_db)):
    return {"earning": _earning(await earnings_service.hold(db, booking_id))}


@router.post("/booking/{booking_id}/release")
async def release_to_shop(booking_id: str, body: DisputeRelease, db: AsyncSession = Depends(get_db)):
    try:
        earning = await earnings_service.release(db, booking_id, body.shop_id, body.total_amount)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return {"earning": _earning(earning)}


@router.post("/booking/{booking_id}/refund")
async def dispute_refund(
    booking_id: str,
    body: DisputeRefund,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    gateway: RazorpayGateway = Depends(get_razorpay),
    notifier: Notifier = Depends(get_notifier),
    sync: BookingSync = Depends(get_booking_sync),
):
    """Refunds a disputed booking's payment, all of what is left or [amount_cents] of it, once per key."""
    earlier = await payment_service.refund_by_key(db, body.idempotency_key)
    if earlier is not None:
        payment = await payment_service.get_payment(db, earlier.payment_id)
        return {"refund_id": earlier.id, "refund_cents": earlier.amount_cents, "payment_status": payment.status}
    payment = await earnings_service.settled_payment(db, booking_id)
    if payment is None or payment.status not in ("COMPLETED", "PARTIALLY_REFUNDED"):
        raise HTTPException(status_code=409, detail="This booking has no payment left to refund")
    left = payment.amount_cents - await payment_service.refunded_cents(db, payment.id)
    amount = body.amount_cents or left
    if amount > left:
        raise HTTPException(status_code=422, detail=f"Only {left} paise are left to refund")
    try:
        refund = await payment_service.request_refund(
            db,
            payment.id,
            RefundRequest(amount_cents=amount, reason=body.reason),
            gateway,
            idempotency_key=body.idempotency_key,
        )
    except GatewayError as e:
        raise HTTPException(status_code=502, detail="Razorpay could not process the refund") from e
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    await earnings_service.release(db, booking_id)  # what is left (if anything) is the shop's again
    await _announce_refund(db, background, notifier, sync, refund, booking_id)
    return {"refund_id": refund.id, "refund_cents": refund.amount_cents, "payment_status": payment.status}
