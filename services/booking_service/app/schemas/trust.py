from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _strip(value):
    return value.strip() if isinstance(value, str) else value


class ExtraItem(BaseModel):
    description: str = Field(min_length=3, max_length=120)
    amount_cents: int = Field(gt=0)

    _strip = field_validator("description", mode="before")(_strip)


class QuoteCreate(BaseModel):
    items: List[ExtraItem] = Field(min_length=1, max_length=10)
    note: Optional[str] = Field(default=None, max_length=500)


class QuoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    booking_id: str
    # PENDING, APPROVED or DECLINED
    status: str
    items: List[ExtraItem]
    total_cents: int
    note: Optional[str] = None
    created_at: datetime
    decided_at: Optional[datetime] = None


class ReworkRequest(BaseModel):
    reason: str = Field(min_length=10, max_length=500)
    # When the customer would like the fix; the shop confirms it (defaults to tomorrow, same time).
    preferred_at: Optional[datetime] = None

    _strip = field_validator("reason", mode="before")(_strip)


class ShareResponse(BaseModel):
    url: str
    expires_at: datetime


class ProviderLocation(BaseModel):
    lat: float
    lng: float
    updated_at: Optional[datetime] = None


class PublicShare(BaseModel):
    """A shared visit as anyone with the link sees it: never a phone, email, full name or address."""

    shop_name: Optional[str] = None
    service_name: Optional[str] = None
    status: str
    scheduled_at: datetime
    provider_first_name: Optional[str] = None
    # Only while the professional is on the way (or bringing a pickup back).
    provider_location: Optional[ProviderLocation] = None
    # When the professional is expected at the door: estimated while they are on the way to a home visit,
    # otherwise the booked time (null once the visit has started or is over).
    eta: Optional[datetime] = None


class SosRequest(BaseModel):
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lng: Optional[float] = Field(default=None, ge=-180, le=180)
    note: Optional[str] = Field(default=None, max_length=500)


class SosResponse(BaseModel):
    alert_id: str
    emergency_number: str = "112"


class SosAlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    booking_id: str
    booking_number: Optional[str] = None
    raised_by: str
    role: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    note: Optional[str] = None
    created_at: datetime


class SosAlertList(BaseModel):
    items: List[SosAlertResponse]
    total: int
    page: int
    per_page: int
