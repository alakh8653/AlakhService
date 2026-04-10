import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ServiceBase(BaseModel):
    name: str
    description: str | None = None
    category: str
    price: Decimal
    duration_minutes: int


class ServiceCreate(ServiceBase):
    image_url: str | None = None


class ServiceRead(ServiceBase):
    id: uuid.UUID
    is_active: bool
    image_url: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ServiceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    category: str | None = None
    price: Decimal | None = None
    duration_minutes: int | None = None
    is_active: bool | None = None
    image_url: str | None = None
