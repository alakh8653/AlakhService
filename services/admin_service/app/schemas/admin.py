from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class AdminUserCreate(BaseModel):
    user_id: str
    role: str = "admin"
    permissions: Optional[List[str]] = None


class AdminUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    role: str
    permissions: Optional[str] = None
    is_active: bool
    created_at: datetime


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    admin_id: str
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    old_values: Optional[str] = None
    new_values: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime


class SystemConfigUpdate(BaseModel):
    value: str
    description: Optional[str] = None
    # Ignored: the acting admin is taken from the access token. Kept for older clients.
    updated_by: Optional[str] = None


class SystemConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    key: str
    value: str
    description: Optional[str] = None
    updated_by: Optional[str] = None
    updated_at: datetime


class BanUserRequest(BaseModel):
    reason: Optional[str] = None
    # Ignored: the acting admin is taken from the access token. Kept for older clients.
    banned_by: Optional[str] = None


class BulkUpdateRequest(BaseModel):
    user_ids: List[str]
    action: str  # "ban", "unban", "verify"
    # Ignored: the acting admin is taken from the access token. Kept for older clients.
    admin_id: Optional[str] = None
    reason: Optional[str] = None
