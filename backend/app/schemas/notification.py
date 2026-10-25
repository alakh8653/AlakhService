import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class NotificationBase(BaseModel):
    title: str
    body: str
    notification_type: str


class NotificationRead(NotificationBase):
    id: uuid.UUID
    is_read: bool
    data: Any | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DeviceTokenRegister(BaseModel):
    device_token: str
    platform: Literal["ios", "android", "web"]
