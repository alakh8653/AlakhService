from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    CalculationNotFoundError,
    CouponAlreadyUsedError,
    CouponExhaustedError,
    CouponExpiredError,
    CouponNotFoundError,
)
from app.core.internal import require_internal
from app.database import get_db
from app.dependencies import Caller, ensure_self_or_admin, require_admin, require_caller
from app.schemas.pricing import (
    CouponCreate,
    CouponResponse,
    CouponValidateResponse,
    PriceCalculationRequest,
    PriceCalculationResponse,
)
from app.services.pricing_service import pricing_service

router = APIRouter()
internal_router = APIRouter(dependencies=[Depends(require_internal)])


@router.post("/pricing/calculate", response_model=PriceCalculationResponse, status_code=201)
async def calculate_price(
    data: PriceCalculationRequest, db: AsyncSession = Depends(get_db), caller: Caller = Depends(require_caller)
):
    ensure_self_or_admin(data.customer_id, caller)
    return await pricing_service.calculate_price(db, data)


@router.get("/pricing/history/{customer_id}", response_model=List[PriceCalculationResponse])
async def get_pricing_history(
    customer_id: str, db: AsyncSession = Depends(get_db), caller: Caller = Depends(require_caller)
):
    ensure_self_or_admin(customer_id, caller)
    return await pricing_service.get_pricing_history(db, customer_id)


@internal_router.post("/internal/pricing/{calculation_id}/redeem", response_model=PriceCalculationResponse)
async def redeem_quote(calculation_id: str, db: AsyncSession = Depends(get_db)):
    """Checkout: commit to a quote, using up its coupon.

    Only booking_service calls this, for the quote it made from the catalogue price while creating
    a booking; open to customers, it let anyone use up a limited coupon without booking anything.
    """
    try:
        calc = await pricing_service.get_calculation(db, calculation_id)
    except CalculationNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    try:
        return await pricing_service.redeem(db, calc)
    except (CouponAlreadyUsedError, CouponExhaustedError, CouponExpiredError) as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.post("/coupons", response_model=CouponResponse, status_code=201, dependencies=[Depends(require_admin)])
async def create_coupon(data: CouponCreate, db: AsyncSession = Depends(get_db)):
    return await pricing_service.create_coupon(db, data)


@router.get("/coupons", response_model=List[CouponResponse], dependencies=[Depends(require_admin)])
async def list_coupons(db: AsyncSession = Depends(get_db)):
    return await pricing_service.list_coupons(db)


@router.get("/coupons/{code}/validate", response_model=CouponValidateResponse)
async def validate_coupon(code: str, db: AsyncSession = Depends(get_db), caller: Caller = Depends(require_caller)):
    try:
        return await pricing_service.validate_coupon(db, code.strip().upper())
    except CouponNotFoundError as e:
        raise HTTPException(status_code=404, detail="Coupon not found") from e
