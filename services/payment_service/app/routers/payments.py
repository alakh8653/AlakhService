from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis
from typing import Optional

from app.database import get_db
from app.dependencies import get_redis, get_current_user
from app.schemas.payment import (
    PaymentInitiate, PaymentResponse,
    RefundRequest, RefundResponse,
    AccountResponse, LedgerEntryResponse,
    WebhookPayload, TransactionHistoryResponse,
)
from app.services.payment_service import payment_service
import structlog

router = APIRouter()
log = structlog.get_logger()


@router.post("/payments/initiate", response_model=PaymentResponse, status_code=201)
async def initiate_payment(
    payment_data: PaymentInitiate,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    current_user: dict = Depends(get_current_user),
):
    try:
        payment = await payment_service.initiate_payment(db, redis, payment_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return payment


@router.get("/payments/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    payment = await payment_service.get_payment(db, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment


@router.post("/payments/{payment_id}/refund", response_model=RefundResponse)
async def request_refund(
    payment_id: str,
    refund_data: RefundRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        refund = await payment_service.request_refund(db, payment_id, refund_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return refund


@router.get("/accounts/{account_id}/balance")
async def get_account_balance(
    account_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
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
        raise HTTPException(status_code=400, detail=str(e))
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
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "processed"}
