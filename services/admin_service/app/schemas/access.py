from datetime import datetime
from typing import List

from pydantic import BaseModel, Field


class PermissionResponse(BaseModel):
    key: str
    resource: str
    description: str


class RoleResponse(BaseModel):
    id: str
    name: str
    description: str
    permissions: List[str]
    is_system: bool
    user_count: int
    created_at: datetime


class RoleCreate(BaseModel):
    name: str = Field(min_length=2, max_length=50, pattern=r"^[a-z][a-z0-9_-]*$")
    description: str = Field(default="", max_length=200)
    permissions: List[str] = []


class RolePermissionsUpdate(BaseModel):
    permissions: List[str]
