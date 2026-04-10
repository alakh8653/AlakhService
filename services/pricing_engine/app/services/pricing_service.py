import uuid
import json
from datetime import datetime, timezone
from typing import List, Optional
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.pricing import PriceCalculation, Coupon
from app.schemas.pricing import PriceCalculationRequest, CouponCreate, CouponValidateResponse
from app.core.rules import PricingContext, pricing_engine
from app.core.exceptions import CouponNotFoundError, CouponExpiredError, CouponExhaustedError

log = structlog.get_logger()


class PricingService:

    async def calculate_price(self, db: AsyncSession, data: PriceCalculationRequest) -> PriceCalculation:
        coupon_discount_pct = 0.0

        if data.coupon_code:
            try:
                validate_result = await self.validate_coupon(db, data.coupon_code)
                if validate_result.is_valid:
                    coupon_discount_pct = validate_result.discount_pct
                    # Increment usage
                    result = await db.execute(select(Coupon).where(Coupon.code == data.coupon_code))
                    coupon = result.scalar_one_or_none()
                    if coupon:
                        coupon.uses_count += 1
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
            created_at=datetime.now(timezone.utc),
        )
        db.add(calc)
        await db.flush()
        log.info("price_calculated", service_id=data.service_id, base=data.base_price_cents, final=result_ctx.final_price_cents)
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
