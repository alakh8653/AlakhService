import json
import uuid
from datetime import datetime, timezone
from typing import List

import structlog
from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    CalculationNotFoundError,
    CouponAlreadyUsedError,
    CouponExhaustedError,
    CouponExpiredError,
    CouponNotFoundError,
)
from app.core.rules import PricingContext, pricing_engine
from app.models.pricing import Coupon, CouponRedemption, PriceCalculation
from app.schemas.pricing import CouponCreate, CouponValidateResponse, PriceCalculationRequest

log = structlog.get_logger()


class PricingService:

    async def calculate_price(self, db: AsyncSession, data: PriceCalculationRequest) -> PriceCalculation:
        coupon_discount_pct = 0.0

        if data.coupon_code:
            try:
                validate_result = await self.validate_coupon(db, data.coupon_code)
                if validate_result.is_valid:
                    # A quote only shows the discount; the coupon is used up on redeem().
                    coupon_discount_pct = validate_result.discount_pct
            except (CouponNotFoundError, CouponExpiredError, CouponExhaustedError):
                pass

        ctx = PricingContext(
            base_price_cents=data.base_price_cents,
            service_id=data.service_id,
            customer_tier=data.customer_tier,
            demand_level=data.demand_level,
            supply_level=data.supply_level,
            time_of_day=data.time_of_day,
            coupon_code=data.coupon_code,
            coupon_discount_pct=coupon_discount_pct,
        )
        result_ctx = pricing_engine.calculate(ctx)

        calc = PriceCalculation(
            id=str(uuid.uuid4()),
            service_id=data.service_id,
            customer_id=data.customer_id,
            base_price_cents=data.base_price_cents,
            final_price_cents=result_ctx.final_price_cents,
            applied_rules=json.dumps(result_ctx.applied_rules),
            demand_level=data.demand_level,
            supply_level=data.supply_level,
            coupon_code=data.coupon_code if coupon_discount_pct else None,
            created_at=datetime.now(timezone.utc),
        )
        db.add(calc)
        await db.flush()
        log.info("price_calculated", service_id=data.service_id, base=data.base_price_cents, final=result_ctx.final_price_cents)
        return calc

    async def get_calculation(self, db: AsyncSession, calculation_id: str) -> PriceCalculation:
        calc = (await db.execute(select(PriceCalculation).where(PriceCalculation.id == calculation_id))).scalar_one_or_none()
        if calc is None:
            raise CalculationNotFoundError()
        return calc

    async def redeem(self, db: AsyncSession, calc: PriceCalculation) -> PriceCalculation:
        """Use up the quote's coupon at checkout: once per quote and once per customer per coupon."""
        if calc.redeemed_at is not None:
            raise CouponAlreadyUsedError("This quote has already been redeemed")
        now = datetime.now(timezone.utc)
        if calc.coupon_code:
            check = await self.validate_coupon(db, calc.coupon_code)
            if not check.is_valid:
                raise CouponExpiredError(check.message)
            coupon = (await db.execute(select(Coupon).where(Coupon.code == calc.coupon_code))).scalar_one()
            used = await db.execute(
                select(CouponRedemption).where(
                    CouponRedemption.coupon_id == coupon.id, CouponRedemption.customer_id == calc.customer_id
                )
            )
            if used.scalar_one_or_none() is not None:
                raise CouponAlreadyUsedError()
            # Count the use in one conditional UPDATE so concurrent redemptions cannot exceed max_uses.
            counted = await db.execute(
                update(Coupon)
                .where(Coupon.id == coupon.id, or_(Coupon.max_uses.is_(None), Coupon.uses_count < Coupon.max_uses))
                .values(uses_count=Coupon.uses_count + 1)
            )
            if counted.rowcount != 1:
                raise CouponExhaustedError()
            db.add(CouponRedemption(coupon_id=coupon.id, customer_id=calc.customer_id, calculation_id=calc.id))
        calc.redeemed_at = now
        try:
            await db.flush()
        except IntegrityError:  # the same customer redeeming concurrently
            await db.rollback()
            raise CouponAlreadyUsedError() from None
        log.info("quote_redeemed", calculation_id=calc.id, coupon=calc.coupon_code)
        return calc

    async def get_pricing_history(self, db: AsyncSession, customer_id: str) -> List[PriceCalculation]:
        result = await db.execute(
            select(PriceCalculation)
            .where(PriceCalculation.customer_id == customer_id)
            .order_by(PriceCalculation.created_at.desc())
        )
        return list(result.scalars().all())

    async def create_coupon(self, db: AsyncSession, data: CouponCreate) -> Coupon:
        coupon = Coupon(
            id=str(uuid.uuid4()),
            code=data.code,
            discount_pct=data.discount_pct,
            max_uses=data.max_uses,
            uses_count=0,
            valid_from=data.valid_from,
            valid_to=data.valid_to,
            is_active=True,
        )
        db.add(coupon)
        await db.flush()
        log.info("coupon_created", code=data.code, discount_pct=data.discount_pct)
        return coupon

    async def validate_coupon(self, db: AsyncSession, code: str) -> CouponValidateResponse:
        result = await db.execute(select(Coupon).where(Coupon.code == code))
        coupon = result.scalar_one_or_none()
        if not coupon:
            raise CouponNotFoundError()

        now = datetime.now(timezone.utc)

        if not coupon.is_active:
            return CouponValidateResponse(code=code, is_valid=False, discount_pct=0.0, message="Coupon is inactive")

        if coupon.valid_from:
            valid_from = coupon.valid_from
            if valid_from.tzinfo is None:
                valid_from = valid_from.replace(tzinfo=timezone.utc)
            if now < valid_from:
                return CouponValidateResponse(code=code, is_valid=False, discount_pct=0.0, message="Coupon not yet valid")

        if coupon.valid_to:
            valid_to = coupon.valid_to
            if valid_to.tzinfo is None:
                valid_to = valid_to.replace(tzinfo=timezone.utc)
            if now > valid_to:
                return CouponValidateResponse(code=code, is_valid=False, discount_pct=0.0, message="Coupon has expired")

        if coupon.max_uses is not None and coupon.uses_count >= coupon.max_uses:
            return CouponValidateResponse(code=code, is_valid=False, discount_pct=0.0, message="Coupon has reached maximum uses")

        return CouponValidateResponse(code=code, is_valid=True, discount_pct=coupon.discount_pct, message="Coupon is valid")


pricing_service = PricingService()
