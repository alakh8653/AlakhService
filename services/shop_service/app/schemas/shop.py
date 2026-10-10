from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


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
    rating: float  # 1.0 - 5.0


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
