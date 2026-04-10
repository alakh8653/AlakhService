from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.database import get_db
from app.schemas.pricing import PriceCalculationRequest, PriceCalculationResponse, CouponCreate, CouponResponse, CouponValidateResponse
from app.services.pricing_service import pricing_service
from app.core.exceptions import CouponNotFoundError, CouponExpiredError, CouponExhaustedError

router = APIRouter()


@router.post("/pricing/calculate", response_model=PriceCalculationResponse, status_code=201)
async def calculate_price(data: PriceCalculationRequest, db: AsyncSession = Depends(get_db)):
    return await pricing_service.calculate_price(db, data)


@router.get("/pricing/history/{customer_id}", response_model=List[PriceCalculationResponse])
async def get_pricing_history(customer_id: str, db: AsyncSession = Depends(get_db)):
    return await pricing_service.get_pricing_history(db, customer_id)


@router.post("/coupons", response_model=CouponResponse, status_code=201)
async def create_coupon(data: CouponCreate, db: AsyncSession = Depends(get_db)):
    return await pricing_service.create_coupon(db, data)


@router.get("/coupons/{code}/validate", response_model=CouponValidateResponse)
async def validate_coupon(code: str, db: AsyncSession = Depends(get_db)):
    return await pricing_service.validate_coupon(db, code)
