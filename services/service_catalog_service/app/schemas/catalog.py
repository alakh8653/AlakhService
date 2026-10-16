from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# AT_SHOP: the customer comes to the shop. AT_HOME: a provider comes to the customer.
# PICKUP_DROP: the item (car, bike, laptop, phone, AC...) is collected, serviced and brought back.
ServiceMode = Literal["AT_SHOP", "AT_HOME", "PICKUP_DROP"]
MAX_FEE_CENTS = 1_000_000


def _unique_modes(modes: Optional[List[str]]) -> Optional[List[str]]:
    if modes is None:
        return None
    if not modes:
        raise ValueError("A service needs at least one way of being delivered")
    return list(dict.fromkeys(modes))


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
    service_modes: List[ServiceMode] = ["AT_SHOP"]
    home_visit_fee_cents: int = Field(0, ge=0, le=MAX_FEE_CENTS)
    pickup_fee_cents: int = Field(0, ge=0, le=MAX_FEE_CENTS)

    @field_validator("service_modes")
    @classmethod
    def _check_modes(cls, v):
        return _unique_modes(v)


class ServiceListingUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price_cents: Optional[int] = None
    duration_minutes: Optional[int] = None
    tags: Optional[List[str]] = None
    is_active: Optional[bool] = None
    service_modes: Optional[List[ServiceMode]] = None
    home_visit_fee_cents: Optional[int] = Field(None, ge=0, le=MAX_FEE_CENTS)
    pickup_fee_cents: Optional[int] = Field(None, ge=0, le=MAX_FEE_CENTS)

    @field_validator("service_modes")
    @classmethod
    def _check_modes(cls, v):
        return _unique_modes(v)


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
    service_modes: List[str] = ["AT_SHOP"]
    home_visit_fee_cents: int = 0
    pickup_fee_cents: int = 0

    @field_validator("service_modes", mode="before")
    @classmethod
    def _split_modes(cls, v):
        return [m for m in v.split(",") if m] if isinstance(v, str) else v


class SearchResult(BaseModel):
    service_id: str
    score: float


class FuzzySearchResult(BaseModel):
    term: str
    distance: int
