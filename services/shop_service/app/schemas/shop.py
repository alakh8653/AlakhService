from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class ShopCreate(BaseModel):
    owner_id: str
    name: str
    category: str
    description: Optional[str] = None
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class ShopUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    city: Optional[str] = None
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
