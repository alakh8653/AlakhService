from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class CategoryCreate(BaseModel):
    name: str
    slug: str
    parent_id: Optional[str] = None
    description: Optional[str] = None


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    slug: str
    parent_id: Optional[str] = None
    description: Optional[str] = None
    is_active: bool


class ServiceListingCreate(BaseModel):
    category_id: Optional[str] = None
    shop_id: str
    name: str
    description: Optional[str] = None
    price_cents: int
    duration_minutes: Optional[int] = None
    tags: Optional[List[str]] = None


class ServiceListingUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price_cents: Optional[int] = None
    duration_minutes: Optional[int] = None
    tags: Optional[List[str]] = None
    is_active: Optional[bool] = None


class ServiceListingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    category_id: Optional[str] = None
    shop_id: str
    name: str
    description: Optional[str] = None
    price_cents: int
    duration_minutes: Optional[int] = None
    tags: Optional[str] = None
    is_active: bool
    created_at: datetime


class SearchResult(BaseModel):
    service_id: str
    score: float


class FuzzySearchResult(BaseModel):
    term: str
    distance: int
