from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator


def not_null(value):
    """For partial updates of a column that always has a value: leave it out to keep it, but not null."""
    if value is None:
        raise ValueError("may be omitted but not null")
    return value


class ShopCreate(BaseModel):
    owner_id: str
    name: str
    category: str
    description: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class ShopUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_active: Optional[bool] = None

    # Only for a value sent explicitly (defaults are not validated); null clears the other fields.
    _required = field_validator("name", "category", "is_active")(not_null)


class ShopResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    owner_id: str
    name: str
    category: str
    description: Optional[str] = None
    rating_avg: float
    rating_count: int
    is_active: bool
    is_verified: bool
    city: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    created_at: datetime

    # What the apps show next to a shop ("4.6 (128)"), so lists need no extra call per shop.
    @computed_field
    @property
    def average_rating(self) -> float:
        return round(self.rating_avg, 1) if self.rating_count else 0.0

    @computed_field
    @property
    def review_count(self) -> int:
        return self.rating_count


class ShopDocumentCreate(BaseModel):
    shop_id: str
    type: str
    url: str


class ShopDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    shop_id: str
    type: str
    url: str
    is_verified: bool


class ShopHoursCreate(BaseModel):
    shop_id: str
    day_of_week: int
    open_time: str
    close_time: str


class ShopHoursResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    shop_id: str
    day_of_week: int
    open_time: str
    close_time: str


class RatingUpdate(BaseModel):
    rating: float = Field(ge=1.0, le=5.0)


class ShopRatingCreate(BaseModel):
    booking_id: str
    # Whole stars (4.0 is accepted as 4); the written review is optional.
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("comment")
    @classmethod
    def blank_is_none(cls, value: Optional[str]) -> Optional[str]:
        return (value or "").strip() or None


class StaffCreate(BaseModel):
    shop_id: str
    name: str = Field(min_length=1, max_length=120)
    email: Optional[str] = None
    phone: Optional[str] = None
    role: str = "staff"
    user_id: Optional[str] = None
    service_ids: List[str] = []


class StaffUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    email: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    user_id: Optional[str] = None
    service_ids: Optional[List[str]] = None
    is_active: Optional[bool] = None

    # null service_ids means none; the other fields always have a value.
    _required = field_validator("name", "role", "is_active")(not_null)


class StaffResponse(BaseModel):
    id: str
    shop_id: str
    user_id: Optional[str] = None
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    role: str
    service_ids: List[str]
    is_active: bool
    created_at: datetime
