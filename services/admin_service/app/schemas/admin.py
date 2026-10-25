from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.origin import MAX_IP, MAX_USER_AGENT, clip


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
    user_agent: Optional[str] = None
    service: str = "admin_service"
    created_at: datetime


class AuditLogReport(BaseModel):
    """An admin action another service carried out, reported to POST /internal/audit-logs."""

    admin_id: str = Field(min_length=1, max_length=128)
    action: str = Field(min_length=1, max_length=100)
    resource_type: str = Field(min_length=1, max_length=100)
    resource_id: Optional[str] = Field(None, max_length=255)
    old_values: Optional[Any] = None
    new_values: Optional[Any] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    service: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")

    # These come from the admin's request, so an odd header is shortened rather than losing the entry.
    @field_validator("ip_address")
    @classmethod
    def _clip_ip(cls, v: Optional[str]) -> Optional[str]:
        return clip(v, MAX_IP)

    @field_validator("user_agent")
    @classmethod
    def _clip_user_agent(cls, v: Optional[str]) -> Optional[str]:
        return clip(v, MAX_USER_AGENT)


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
