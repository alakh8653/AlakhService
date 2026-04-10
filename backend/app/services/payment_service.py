import hashlib
import hmac
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import NotFoundException, PaymentException
from app.models.payment import Payment
from app.schemas.payment import PaymentVerify
from app.services.booking_service import get_booking


async def initiate_payment(
    db: AsyncSession, booking_id: uuid.UUID, user_id: uuid.UUID
) -> Payment:
    """Create a PENDING payment record and return it (integrate with gateway here)."""
    booking = await get_booking(db, booking_id)
    # TODO: call Razorpay / Stripe SDK to create a gateway order
    gateway_order_id = f"order_{uuid.uuid4().hex}"
    payment = Payment(
        booking_id=booking.id,
        amount=booking.total_amount,
        currency="INR",
        status="PENDING",
        payment_gateway="razorpay",
        gateway_order_id=gateway_order_id,
    )
    db.add(payment)
    await db.flush()
    await db.refresh(payment)
    return payment


async def verify_payment(db: AsyncSession, payment_verify: PaymentVerify) -> Payment:
    """Verify the gateway signature and mark the payment as SUCCESS or FAILED."""
    result = await db.execute(
        select(Payment).where(
            Payment.gateway_order_id == payment_verify.gateway_order_id
        )
    )
    payment = result.scalar_one_or_none()
    if not payment:
        raise NotFoundException(resource_name="Payment")

    # Razorpay signature verification (HMAC-SHA256 using webhook secret)
    body = f"{payment_verify.gateway_order_id}|{payment_verify.gateway_payment_id}"
    expected_sig = hmac.new(
        settings.RAZORPAY_WEBHOOK_SECRET.encode(), body.encode(), hashlib.sha256
    ).hexdigest()
    if hmac.compare_digest(expected_sig, payment_verify.gateway_signature):
        payment.status = "SUCCESS"
        payment.gateway_payment_id = payment_verify.gateway_payment_id
        payment.gateway_signature = payment_verify.gateway_signature
    else:
        payment.status = "FAILED"
    await db.flush()
    await db.refresh(payment)
    return payment


async def get_payment(db: AsyncSession, payment_id: uuid.UUID) -> Payment:
    result = await db.execute(select(Payment).where(Payment.id == payment_id))
    payment = result.scalar_one_or_none()
    if not payment:
        raise NotFoundException(resource_name="Payment")
    return payment


async def get_user_payments(
    db: AsyncSession, user_id: uuid.UUID, skip: int = 0, limit: int = 20
) -> list[Payment]:
    from app.models.booking import Booking  # local import to avoid circular
    result = await db.execute(
        select(Payment)
        .join(Booking, Payment.booking_id == Booking.id)
        .where(Booking.user_id == user_id)
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


async def process_refund(db: AsyncSession, payment_id: uuid.UUID) -> Payment:
    """Mark a payment as REFUNDED (integrate with gateway refund API here)."""
    payment = await get_payment(db, payment_id)
    if payment.status != "SUCCESS":
        raise PaymentException()
    # TODO: call gateway refund API
    payment.status = "REFUNDED"
    await db.flush()
    await db.refresh(payment)
    return payment


async def handle_webhook(
    db: AsyncSession, payload: bytes, signature: str
) -> dict[str, Any]:
    """Handle payment gateway webhook. Verify signature and update payment status."""
    # TODO: verify webhook signature per gateway docs, then dispatch to verify_payment
    return {"status": "received"}
