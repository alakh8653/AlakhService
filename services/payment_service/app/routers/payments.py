
import redis.asyncio as aioredis
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.schemas.payment import (
    PaymentCheckout,
    PaymentInitiate,
    PaymentResponse,
    RefundRequest,
    RefundResponse,
    TransactionHistoryResponse,
    WebhookPayload,
)
from app.services.payment_service import payment_service

router = APIRouter()
log = structlog.get_logger()


# A booking can be paid for once it is confirmed and until it is completed.
PAYABLE_STATUSES = {"CONFIRMED", "ASSIGNED", "PROVIDER_EN_ROUTE", "IN_PROGRESS", "COMPLETED"}


@router.post("/payments/initiate", response_model=PaymentResponse, status_code=201)
async def initiate_payment(
    checkout: PaymentCheckout,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    current_user: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    lookup_booking: BookingLookup = Depends(get_booking_lookup),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
):
    """Pay for one of your bookings. The amount and the payee come from the booking itself."""
    payer_id = current_user["sub"]
    booking = await lookup_booking(checkout.booking_id, credentials.credentials)
    if booking is None or booking.get("customer_id") != payer_id:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.get("status") not in PAYABLE_STATUSES:
        raise HTTPException(status_code=409, detail="This booking cannot be paid for yet")
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
    return payment


def _ensure_party(payment, current_user: dict) -> None:
    if current_user.get("role") != "admin" and current_user["sub"] not in (payment.payer_id, payment.payee_id):
        raise HTTPException(status_code=404, detail="Payment not found")


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


@router.post("/payments/{payment_id}/refund", response_model=RefundResponse)
async def request_refund(
    payment_id: str,
    refund_data: RefundRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Refunds move money out of escrow, so they are issued by admins (e.g. resolving a dispute)."""
    try:
        refund = await payment_service.request_refund(db, payment_id, refund_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return refund


def _ensure_own_account(account_id: str, current_user: dict) -> None:
    if current_user.get("role") != "admin" and account_id != current_user["sub"]:
        raise HTTPException(status_code=404, detail="Account not found")


@router.get("/accounts/{account_id}/balance")
async def get_account_balance(
    account_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _ensure_own_account(account_id, current_user)
    balance = await payment_service.get_account_balance(db, account_id)
    return {"account_id": account_id, "balance_cents": balance}


@router.get("/accounts/{account_id}/transactions", response_model=TransactionHistoryResponse)
async def get_transaction_history(
    account_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _ensure_own_account(account_id, current_user)
    result = await payment_service.get_transaction_history(db, account_id, page, per_page)
    return result


@router.post("/webhooks/razorpay")
async def razorpay_webhook(
    body: WebhookPayload,
    db: AsyncSession = Depends(get_db),
):
    try:
        await payment_service.process_razorpay_webhook(db, body.payload, body.signature)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"status": "processed"}


@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    body = await request.body()
    signature = request.headers.get("stripe-signature", "")
    try:
        await payment_service.process_stripe_webhook(db, body, signature)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"status": "processed"}
