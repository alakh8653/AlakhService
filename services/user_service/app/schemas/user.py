from datetime import date, datetime
from typing import List, Optional, Literal
from pydantic import BaseModel, ConfigDict


class UserProfileCreate(BaseModel):
    full_name: Optional[str] = None
    bio: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    language: Optional[str] = None
    timezone: Optional[str] = None


class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    bio: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    language: Optional[str] = None
    timezone: Optional[str] = None


class UserProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    language: str
    timezone: str
    created_at: datetime
    updated_at: datetime


class UserAddressCreate(BaseModel):
    label: str
    street: str
    city: str
    state: str
    postal_code: str
    country: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class UserAddressUpdate(BaseModel):
    label: Optional[str] = None
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class UserAddressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    label: str
    street: str
    city: str
    state: str
    postal_code: str
    country: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_default: bool
    created_at: datetime
    updated_at: datetime


class UserPreferencesUpdate(BaseModel):
    notifications_enabled: Optional[bool] = None
    push_enabled: Optional[bool] = None
    email_enabled: Optional[bool] = None
    sms_enabled: Optional[bool] = None
    language: Optional[str] = None
    currency: Optional[str] = None
    theme: Optional[str] = None


class UserPreferencesResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    notifications_enabled: bool
    push_enabled: bool
    email_enabled: bool
    sms_enabled: bool
    language: str
    currency: str
    theme: str
    created_at: datetime
    updated_at: datetime


class UserDeviceCreate(BaseModel):
    device_token: str
    platform: Literal["ios", "android", "web"]
    device_id: str


class UserDeviceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    device_token: str
    platform: str
    device_id: str
    is_active: bool
    last_seen: Optional[datetime] = None
    created_at: datetime


class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    per_page: int
    pages: int
