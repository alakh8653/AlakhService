from __future__ import annotations
import json
from typing import List, Optional, Any
from pydantic import BaseModel, ConfigDict, field_validator

class ServiceCategoryBase(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    icon_url: Optional[str] = None
    parent_id: Optional[str] = None
    order: int = 0
    is_active: bool = True

class ServiceCategoryCreate(ServiceCategoryBase):
    pass

class ServiceCategoryUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    icon_url: Optional[str] = None
    parent_id: Optional[str] = None
    order: Optional[int] = None
    is_active: Optional[bool] = None

class ServiceCategoryResponse(ServiceCategoryBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    children: List[ServiceCategoryResponse] = []

ServiceCategoryResponse.model_rebuild()

class PricingTierBase(BaseModel):
    name: str
    description: Optional[str] = None
    price_cents: int
    features: Optional[List[str]] = None
    is_popular: bool = False

class PricingTierCreate(PricingTierBase):
    pass

class PricingTierResponse(PricingTierBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    service_id: str
    @field_validator("features", mode="before")
    @classmethod
    def parse_features(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return []
        return v or []

class ServiceMediaBase(BaseModel):
    media_type: str
    url: str
    alt_text: Optional[str] = None
    order: int = 0

class ServiceMediaCreate(ServiceMediaBase):
    pass

class ServiceMediaResponse(ServiceMediaBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    service_id: str

class ServiceVariantBase(BaseModel):
    name: str
    price_modifier_cents: int = 0
    duration_modifier_minutes: int = 0
    is_available: bool = True

class ServiceVariantCreate(ServiceVariantBase):
    pass

class ServiceVariantResponse(ServiceVariantBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    service_id: str

class ServiceItemBase(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    base_price_cents: int
    currency: str = "INR"
    duration_minutes: int = 60
    is_active: bool = True
    is_featured: bool = False
    metadata: Optional[Any] = None

class ServiceItemCreate(ServiceItemBase):
    category_id: Optional[str] = None

class ServiceItemUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[str] = None
    base_price_cents: Optional[int] = None
    currency: Optional[str] = None
    duration_minutes: Optional[int] = None
    is_active: Optional[bool] = None
    is_featured: Optional[bool] = None

class ServiceItemResponse(ServiceItemBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    category_id: Optional[str] = None
    booking_count: int = 0
    pricing_tiers: List[PricingTierResponse] = []
    media: List[ServiceMediaResponse] = []
    variants: List[ServiceVariantResponse] = []
    @field_validator("metadata", mode="before")
    @classmethod
    def parse_metadata(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return {}
        return v

class ServiceItemListResponse(BaseModel):
    items: List[ServiceItemResponse]
    total: int
    page: int
    per_page: int

class SearchCatalogParams(BaseModel):
    query: Optional[str] = None
    category_id: Optional[str] = None
    min_price_cents: Optional[int] = None
    max_price_cents: Optional[int] = None
    page: int = 1
    per_page: int = 20
