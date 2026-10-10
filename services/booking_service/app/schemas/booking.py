from datetime import date, datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, field_validator


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


class BookingCancelRequest(BaseModel):
    reason: str


class BookingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    booking_number: str
    customer_id: str
    provider_id: Optional[str] = None
    service_id: str
    shop_id: Optional[str] = None
    status: str
    scheduled_at: datetime
    duration_minutes: int
    address_id: Optional[str] = None
    notes: Optional[str] = None
    total_amount: int
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
