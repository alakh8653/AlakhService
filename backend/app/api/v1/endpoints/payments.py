from uuid import UUID
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_active_user
from app.models.user import User
from app.schemas.payment import PaymentInitiate, PaymentRead, PaymentVerify
from app.services.payment_service import (
    get_payment,
    get_user_payments,
    handle_webhook,
    initiate_payment,
    verify_payment,
)
from app.api.v1.dependencies import pagination_params

router = APIRouter()


@router.post("/initiate", response_model=PaymentRead, status_code=status.HTTP_201_CREATED)
async def initiate(
    payment_initiate: PaymentInitiate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Initiate a payment for a booking and return gateway order details."""
    return await initiate_payment(
        db, booking_id=payment_initiate.booking_id, user_id=current_user.id
    )


@router.post("/verify")
async def verify(
    payment_verify: PaymentVerify,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Verify a payment after receiving a callback from the payment gateway."""
    return await verify_payment(db, payment_verify=payment_verify)


@router.get("/{payment_id}", response_model=PaymentRead)
async def get_payment_detail(
    payment_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get details for a specific payment."""
    return await get_payment(db, payment_id=payment_id)


@router.get("/", response_model=list[PaymentRead])
async def list_payments(
    pagination: dict = Depends(pagination_params),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """List all payments for the current user."""
    return await get_user_payments(
        db, user_id=current_user.id, skip=pagination["skip"], limit=pagination["limit"]
    )


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle incoming webhook events from the payment gateway."""
    payload = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")
    return await handle_webhook(db, payload=payload, signature=signature)
