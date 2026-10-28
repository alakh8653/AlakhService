from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# How far in the past a new booking may start, so a client clock running slightly behind is not refused.
SCHEDULE_CLOCK_SKEW = timedelta(minutes=5)


def _not_in_past(v: datetime) -> datetime:
    at = v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if at < datetime.now(timezone.utc) - SCHEDULE_CLOCK_SKEW:
        raise ValueError("scheduled_at must not be in the past")
    return v


class BookingCreate(BaseModel):
    # Ignored by the API: the customer is the caller.
    customer_id: Optional[str] = None
    service_id: str
    # Ignored by the API: the shop, price and (when listed) duration come from the service catalogue.
    shop_id: Optional[str] = None
    scheduled_at: datetime
    duration_minutes: Optional[int] = None
    address_id: Optional[str] = None
    notes: Optional[str] = None
    total_amount: Optional[int] = None
    # A promo code; the booking is priced with its discount (pricing_engine) and the code is used up.
    coupon_code: Optional[str] = Field(default=None, max_length=50)
    # How it is delivered: at the shop, at the customer's address, or by collecting the item from
    # there and bringing it back. Must be one the service offers; the last two need address_id.
    service_mode: Literal["AT_SHOP", "AT_HOME", "PICKUP_DROP"] = "AT_SHOP"
    # What is being collected and what is wrong with it (pickup & drop).
    item_description: Optional[str] = Field(default=None, max_length=500)
    # Spend the customer's loyalty points on it (up to a share of the price; the platform pays for them).
    use_points: bool = False

    @field_validator("scheduled_at")
    @classmethod
    def validate_scheduled_at(cls, v: datetime) -> datetime:
        return _not_in_past(v)

    @field_validator("duration_minutes")
    @classmethod
    def validate_duration(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("duration_minutes must be greater than 0")
        return v

    @field_validator("total_amount")
    @classmethod
    def validate_amount(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("total_amount must be greater than 0")
        return v


class BookingStatusUpdate(BaseModel):
    status: str
    reason: Optional[str] = None


class BookingAssignRequest(BaseModel):
    provider_id: str


class BookingReadyByUpdate(BaseModel):
    # When the item should be back with the customer; null clears it.
    ready_by: Optional[datetime] = None


class BookingCancelRequest(BaseModel):
    reason: str


class BookingRescheduleRequest(BaseModel):
    # The new start; the service, price and duration stay as booked.
    scheduled_at: datetime
    reason: Optional[str] = Field(default=None, max_length=300)

    @field_validator("scheduled_at")
    @classmethod
    def validate_scheduled_at(cls, v: datetime) -> datetime:
        return _not_in_past(v)


class BookingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    booking_number: str
    customer_id: str
    # What the shop calls the customer: first name and last initial ("Ravi S."), or "Customer". The
    # customer's phone, email and full name are never part of a booking (see app/core/privacy.py).
    customer_display_name: str = "Customer"
    provider_id: Optional[str] = None
    service_id: str
    shop_id: Optional[str] = None
    status: str
    scheduled_at: datetime
    duration_minutes: int
    address_id: Optional[str] = None
    service_mode: str = "AT_SHOP"
    item_description: Optional[str] = None
    ready_by: Optional[datetime] = None
    notes: Optional[str] = None
    total_amount: int
    list_price: Optional[int] = None
    # Home visit or pickup fee included in total_amount.
    service_mode_fee: int = 0
    coupon_code: Optional[str] = None
    # Paid by the customer's loyalty points (included in list_price, not in total_amount).
    points_discount: int = 0
    # Times the customer has moved it (they may do so MAX_CUSTOMER_RESCHEDULES times).
    reschedule_count: int = 0
    # UNPAID, PAID, REFUNDED or PARTIALLY_REFUNDED (kept up to date by payment_service).
    payment_status: str = "UNPAID"
    created_at: datetime
    updated_at: datetime


class BookingStatusHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    booking_id: str
    from_status: Optional[str] = None
    to_status: str
    changed_by: str
    reason: Optional[str] = None
    created_at: datetime


class BookingListResponse(BaseModel):
    items: List[BookingResponse]
    total: int
    page: int
    per_page: int


class DailyBookingRevenue(BaseModel):
    day: date
    revenue: int  # cents, completed bookings
    bookings: int


class ServiceBookingStats(BaseModel):
    service_id: str
    bookings: int
    revenue: int  # cents, completed bookings


class ShopBookingSummary(BaseModel):
    shop_id: str
    date_from: date
    date_to: date
    total_bookings: int
    total_revenue: int  # cents, completed bookings
    unique_customers: int
    by_status: Dict[str, int]
    by_day: List[DailyBookingRevenue]
    top_services: List[ServiceBookingStats]


class PaymentStatusUpdate(BaseModel):
    payment_status: Literal["UNPAID", "PAID", "REFUNDED", "PARTIALLY_REFUNDED"]


class DisputeResolution(BaseModel):
    outcome: Literal["COMPLETED", "REFUNDED"]
