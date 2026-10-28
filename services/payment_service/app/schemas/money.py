from datetime import date, datetime
from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class CommissionUpdate(BaseModel):
    # null removes the shop's own rate (or the platform default's override), going back to the default.
    commission_percent: Optional[Decimal] = Field(default=None, ge=0, le=50, decimal_places=2)


class CommissionOverride(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    shop_id: str
    commission_percent: Decimal
    updated_by: Optional[str] = None
    updated_at: Optional[datetime] = None

    @field_serializer("commission_percent")
    def _pct(self, v: Decimal) -> float:
        return float(v)


class CommissionSettings(BaseModel):
    default_commission_percent: float
    configured_default_percent: float
    gst_on_commission_percent: float
    overrides: List[CommissionOverride]


class ShopCommission(BaseModel):
    shop_id: str
    commission_percent: float
    gst_on_commission_percent: float
    source: Literal["shop", "default"]


class PayoutResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    batch_id: str
    shop_id: str
    period_from: Optional[date] = None
    period_to: date
    amount_cents: int
    currency: str
    status: str
    paid_at: Optional[datetime] = None
    reference: Optional[str] = None
    created_at: datetime


class ShopPayout(BaseModel):
    """A payout as the contract shows it to shops (amount in rupees)."""

    id: str
    period_from: Optional[date] = None
    period_to: date
    amount: float
    status: str
    paid_at: Optional[datetime] = None
    reference: Optional[str] = None


class PayoutList(BaseModel):
    data: List[PayoutResponse]
    total: int
    page: int
    per_page: int


class PayoutBatchCreate(BaseModel):
    # Everything completed up to and including this day (default: yesterday, so today's work is complete).
    period_to: Optional[date] = None
    shop_ids: Optional[List[str]] = None


class PayoutBatchResponse(BaseModel):
    batch_id: str
    payouts: List[PayoutResponse]
    total_amount_cents: int


class MarkPaid(BaseModel):
    reference: str = Field(min_length=3, max_length=100)


class LoyaltyRedeem(BaseModel):
    """booking_service spending a customer's points on a booking it is making."""

    customer_id: str
    booking_id: str
    price_cents: int = Field(ge=0)


class LoyaltyRelease(BaseModel):
    booking_id: str


class BookingCompleted(BaseModel):
    shop_id: Optional[str] = None
    # Who earns loyalty points on it (older booking_service messages leave it out: no points).
    customer_id: Optional[str] = None
    total_amount: Optional[int] = Field(default=None, ge=0)
    completed_at: Optional[datetime] = None


class BookingCancelled(BaseModel):
    cancelled_by: Literal["customer", "shop", "admin"]
    scheduled_at: Optional[datetime] = None
    # When the cancel happened; a retried call is judged by it, not by when the retry arrives.
    cancelled_at: Optional[datetime] = None


class DisputeRefund(BaseModel):
    # null refunds everything that is left.
    amount_cents: Optional[int] = Field(default=None, gt=0)
    reason: str = Field(min_length=1, max_length=500)
    idempotency_key: str = Field(min_length=8, max_length=128)


class DisputeRelease(BaseModel):
    shop_id: Optional[str] = None
    total_amount: Optional[int] = Field(default=None, ge=0)
