from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class PriceCalculationRequest(BaseModel):
    service_id: str
    customer_id: str
    base_price_cents: int
    customer_tier: str = "regular"
    demand_level: float = 1.0
    supply_level: float = 1.0
    time_of_day: int = 12
    coupon_code: Optional[str] = None


class PriceCalculationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    service_id: str
    customer_id: str
    base_price_cents: int
    final_price_cents: int
    applied_rules: Optional[str] = None
    demand_level: float
    supply_level: float
    created_at: datetime


class CouponCreate(BaseModel):
    code: str
    discount_pct: float
    max_uses: Optional[int] = None
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None


class CouponResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    code: str
    discount_pct: float
    max_uses: Optional[int] = None
    uses_count: int
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    is_active: bool


class CouponValidateResponse(BaseModel):
    code: str
    is_valid: bool
    discount_pct: float
    message: str
