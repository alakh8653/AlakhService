from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, field_validator


class BookingCreate(BaseModel):
    customer_id: str
    service_id: str
    scheduled_at: datetime
    duration_minutes: int
    address_id: Optional[str] = None
    notes: Optional[str] = None
    total_amount: int

    @field_validator("duration_minutes")
    @classmethod
    def validate_duration(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("duration_minutes must be greater than 0")
        return v

    @field_validator("total_amount")
    @classmethod
    def validate_amount(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("total_amount must be greater than 0")
        return v


class BookingStatusUpdate(BaseModel):
    status: str
    reason: Optional[str] = None


class BookingCancelRequest(BaseModel):
    reason: str


class BookingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    booking_number: str
    customer_id: str
    provider_id: Optional[str] = None
    service_id: str
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
