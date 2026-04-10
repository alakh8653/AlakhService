from __future__ import annotations
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class NotificationTemplateCreate(BaseModel):
    name: str
    channel: str
    subject_template: Optional[str] = None
    body_template: str
    variables: Optional[List[str]] = None


class NotificationTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    channel: str
    subject_template: Optional[str] = None
    body_template: str
    variables: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class NotificationCreate(BaseModel):
    user_id: str
    template_name: str
    variables: Dict[str, Any] = {}
    channels: Optional[List[str]] = None
    priority: str = "normal"


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    channel: str
    template_id: Optional[str] = None
    status: str
    title: str
    body: str
    data: Optional[str] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    failed_reason: Optional[str] = None
    retry_count: int
    is_read: bool
    created_at: datetime
    updated_at: datetime


class NotificationListResponse(BaseModel):
    items: List[NotificationResponse]
    total: int
    page: int
    per_page: int


class NotificationPreferenceCreate(BaseModel):
    user_id: str
    channel: str
    is_enabled: bool = True
    quiet_hours_start: Optional[int] = None
    quiet_hours_end: Optional[int] = None


class NotificationPreferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    channel: str
    is_enabled: bool
    quiet_hours_start: Optional[int] = None
    quiet_hours_end: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class DeviceTokenCreate(BaseModel):
    user_id: str
    token: str
    platform: str


class DeviceTokenResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    token: str
    platform: str
    is_active: bool
    created_at: datetime
