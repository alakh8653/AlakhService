import json
from datetime import datetime, timezone
from typing import List, Optional

import redis.asyncio as aioredis
import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core import risk
from app.core.notifier import Notifier, get_notifier, notify_payment, payment_snapshot
from app.core.razorpay import GatewayError, RazorpayGateway, get_razorpay
from app.database import get_db
from app.dependencies import (
    BookingLookup,
    OwnerLookup,
    get_booking_lookup,
    get_current_user,
    get_redis,
    get_shop_owner_lookup,
    require_admin,
    security,
)
from app.models.payment import Payment
from app.schemas.payment import (
    PaymentCheckout,
    PaymentCheckoutResponse,
    PaymentInitiate,
    PaymentResponse,
    RazorpayCheckout,
    RazorpayVerification,
    RefundRequest,
    RefundResponse,
    TransactionHistoryResponse,
)
from app.services.payment_service import PAID_STATUSES, payment_service

router = APIRouter()
log = structlog.get_logger()


# A booking can be paid for once it is confirmed and until it is completed.
PAYABLE_STATUSES = {
    "CONFIRMED",
    "ASSIGNED",
    "PROVIDER_EN_ROUTE",
    "PICKED_UP",
    "IN_PROGRESS",
    "OUT_FOR_DELIVERY",
    "COMPLETED",
}


def _report_risk_after(background: BackgroundTasks, event: Optional[str], payment: Payment) -> None:
    signal = risk.PAYMENT_SIGNALS.get(event)
    if signal:
        background.add_task(risk.report_risk, payment.payer_id, *signal)


def _with_checkout(payment: Payment, gateway: RazorpayGateway) -> PaymentCheckoutResponse:
    response = PaymentCheckoutResponse.model_validate(payment)
    if payment.status == "PENDING" and payment.provider_order_id:
        response.checkout = RazorpayCheckout(
            key_id=gateway.key_id,
            order_id=payment.provider_order_id,
            amount_cents=payment.amount_cents,
            currency=payment.currency,
        )
    return response


@router.post("/payments/initiate", response_model=PaymentCheckoutResponse, status_code=201)
async def initiate_payment(
    checkout: PaymentCheckout,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    current_user: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    lookup_booking: BookingLookup = Depends(get_booking_lookup),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
    gateway: RazorpayGateway = Depends(get_razorpay),
):
    """Pay for one of your bookings. The amount and the payee come from the booking itself.

    Online methods return a Razorpay order for the app's checkout; the payment completes once
    Razorpay confirms it (``/payments/{id}/verify`` or the webhook). Cash stays pending until settled.
    """
    payer_id = current_user["sub"]
    online = checkout.payment_method != "cash"
    if online and not gateway.configured:
        raise HTTPException(status_code=503, detail="Online payments are not available yet. Please pay in cash.")
    booking = await lookup_booking(checkout.booking_id, credentials.credentials)
    if booking is None or booking.get("customer_id") != payer_id:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.get("status") not in PAYABLE_STATUSES:
        raise HTTPException(status_code=409, detail="This booking cannot be paid for yet")
    # One booking is paid for once; a retry with the same key still returns its payment below.
    for earlier in await payment_service.payments_for_booking(db, checkout.booking_id):
        if earlier.status in PAID_STATUSES and earlier.idempotency_key != checkout.idempotency_key:
            raise HTTPException(status_code=409, detail="This booking has already been paid for")
    payee_id = await lookup_owner(booking["shop_id"]) if booking.get("shop_id") else booking.get("provider_id")
    if not payee_id:
        raise HTTPException(status_code=409, detail="This booking has no one to pay yet")
    payment_data = PaymentInitiate(
        booking_id=checkout.booking_id,
        payer_id=payer_id,
        payee_id=payee_id,
        amount_cents=booking["total_amount"],
        payment_method=checkout.payment_method,
        idempotency_key=checkout.idempotency_key,
    )
    try:
        payment = await payment_service.initiate_payment(db, redis, payment_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    # An idempotency key belongs to whoever used it first; it never reveals someone else's payment.
    if payment.payer_id != payer_id:
        raise HTTPException(status_code=409, detail="Idempotency key already used")
    if payment.payment_method != "cash" and payment.status == "PENDING" and not payment.provider_order_id:
        try:
            payment.provider_order_id = await gateway.create_order(
                payment.amount_cents,
                payment.currency,
                receipt=payment.id,
                notes={"payment_id": payment.id, "booking_id": payment.booking_id},
            )
        except GatewayError as e:
            log.warning("razorpay_order_failed", payment_id=payment.id, error=str(e))
            raise HTTPException(status_code=502, detail="Could not start the payment. Please try again.") from e
        payment.updated_at = datetime.now(timezone.utc)
        await db.flush()
    return _with_checkout(payment, gateway)


@router.post("/payments/{payment_id}/verify", response_model=PaymentCheckoutResponse)
async def verify_payment(
    payment_id: str,
    proof: RazorpayVerification,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    gateway: RazorpayGateway = Depends(get_razorpay),
    notifier: Notifier = Depends(get_notifier),
):
    """Confirms a checkout with the signature Razorpay gave the app; only a valid signature completes it."""
    payment = await payment_service.get_payment(db, payment_id)
    if not payment or payment.payer_id != current_user["sub"]:
        raise HTTPException(status_code=404, detail="Payment not found")
    if (
        not payment.provider_order_id
        or proof.razorpay_order_id != payment.provider_order_id
        or not gateway.checkout_signature_valid(
            proof.razorpay_order_id, proof.razorpay_payment_id, proof.razorpay_signature
        )
    ):
        raise HTTPException(status_code=400, detail="Payment could not be verified")
    changed = await payment_service.record_capture(db, payment, proof.razorpay_payment_id, "razorpay", gateway)
    await db.commit()  # visible before anyone is told (the background task delays the session's commit)
    if changed:
        background.add_task(notify_payment, notifier, changed, payment_snapshot(payment))
        _report_risk_after(background, changed, payment)
    return _with_checkout(payment, gateway)


def _ensure_party(payment, current_user: dict) -> None:
    if current_user.get("role") != "admin" and current_user["sub"] not in (payment.payer_id, payment.payee_id):
        raise HTTPException(status_code=404, detail="Payment not found")


@router.get("/payments", response_model=List[PaymentResponse])
async def list_payments(
    booking_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Payments for a booking (all of them for admins, otherwise those the caller paid or received),
    or without a booking id the caller's own recent payments."""
    if booking_id is None:
        return await payment_service.payments_by_payer(db, current_user["sub"])
    payments = await payment_service.payments_for_booking(db, booking_id)
    if current_user.get("role") != "admin":
        payments = [p for p in payments if current_user["sub"] in (p.payer_id, p.payee_id)]
    return payments


@router.get("/payments/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    payment = await payment_service.get_payment(db, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    _ensure_party(payment, current_user)
    return payment


@router.post("/payments/{payment_id}/cash-received", response_model=PaymentResponse)
async def confirm_cash_received(
    payment_id: str,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    notifier: Notifier = Depends(get_notifier),
):
    """The shop (payee) confirms a cash payment was handed over, completing it."""
    payment = await payment_service.get_payment(db, payment_id)
    if (
        not payment
        or current_user["sub"] not in (payment.payee_id, payment.payer_id)
        and current_user.get("role") != "admin"
    ):
        raise HTTPException(status_code=404, detail="Payment not found")
    if current_user["sub"] != payment.payee_id and current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Only the shop that was paid can confirm cash")
    if payment.payment_method != "cash":
        raise HTTPException(status_code=409, detail="Only cash payments are confirmed by hand")
    if payment.status != "PENDING":
        raise HTTPException(status_code=409, detail=f"Payment is already {payment.status.lower()}")
    await payment_service.mark_completed(db, payment, None, "cash")
    await db.commit()  # visible before anyone is told
    background.add_task(notify_payment, notifier, "payment.completed", payment_snapshot(payment))
    _report_risk_after(background, "payment.completed", payment)
    return payment


@router.post("/payments/{payment_id}/refund", response_model=RefundResponse)
async def request_refund(
    payment_id: str,
    refund_data: RefundRequest,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
    gateway: RazorpayGateway = Depends(get_razorpay),
    notifier: Notifier = Depends(get_notifier),
):
    """Refunds move money out of escrow, so they are issued by admins (e.g. resolving a dispute).

    Card/UPI payments are refunded through Razorpay; cash refunds are recorded as MANUAL.
    """
    try:
        refund = await payment_service.request_refund(db, payment_id, refund_data, gateway)
    except GatewayError as e:
        log.warning("razorpay_refund_failed", payment_id=payment_id, error=str(e))
        raise HTTPException(status_code=502, detail="Razorpay could not process the refund") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    payment = await payment_service.get_payment(db, payment_id)
    await db.commit()  # visible before the customer is told
    background.add_task(
        notify_payment, notifier, "payment.refunded", {**payment_snapshot(payment), "amount_cents": refund.amount_cents}
    )
    return refund


async def _own_ledger_account(db: AsyncSession, account_id: str, current_user: dict) -> Optional[str]:
    """The ledger account id behind [account_id]: callers name theirs by their user id or its account id.

    Admins name any account by its account id. None means the caller has no account yet.
    """
    if current_user.get("role") == "admin":
        return account_id
    account = await payment_service.account_for_owner(db, current_user["sub"])
    if account_id != current_user["sub"] and (account is None or account_id != account.id):
        raise HTTPException(status_code=404, detail="Account not found")
    return account.id if account else None


@router.get("/accounts/{account_id}/balance")
async def get_account_balance(
    account_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    ledger_account_id = await _own_ledger_account(db, account_id, current_user)
    balance = await payment_service.get_account_balance(db, ledger_account_id) if ledger_account_id else 0
    return {"account_id": account_id, "balance_cents": balance}


@router.get("/accounts/{account_id}/transactions", response_model=TransactionHistoryResponse)
async def get_transaction_history(
    account_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    ledger_account_id = await _own_ledger_account(db, account_id, current_user)
    if ledger_account_id is None:
        return {"items": [], "total": 0, "page": page, "per_page": per_page}
    return await payment_service.get_transaction_history(db, ledger_account_id, page, per_page)


@router.post("/webhooks/razorpay")
async def razorpay_webhook(
    request: Request,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    gateway: RazorpayGateway = Depends(get_razorpay),
    notifier: Notifier = Depends(get_notifier),
):
    """Razorpay events, signed over the raw body with the webhook secret. Unsigned calls are refused."""
    if not gateway.webhook_secret:
        raise HTTPException(status_code=503, detail="Razorpay webhooks are not configured")
    body = await request.body()
    if not gateway.webhook_signature_valid(body, request.headers.get("x-razorpay-signature", "")):
        raise HTTPException(status_code=400, detail="Invalid signature")
    event = json.loads(body)
    if str(event.get("event", "")).startswith("refund."):
        await payment_service.process_refund_event(db, event)
        return {"status": "processed"}
    changed = await payment_service.process_razorpay_event(db, event, gateway)
    if changed:
        event, payment = changed
        await db.commit()  # visible before anyone is told (the background task delays the session's commit)
        background.add_task(notify_payment, notifier, event, payment_snapshot(payment))
        _report_risk_after(background, event, payment)
    return {"status": "processed"}


@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Stripe events, accepted only with a valid Stripe-Signature."""
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Stripe webhooks are not configured")
    import stripe

    body = await request.body()
    try:
        stripe.Webhook.construct_event(
            body, request.headers.get("stripe-signature", ""), settings.STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid signature") from e
    changed = await payment_service.process_stripe_event(db, json.loads(body))
    if changed:
        await db.commit()
        _report_risk_after(background, *changed)
    return {"status": "processed"}
