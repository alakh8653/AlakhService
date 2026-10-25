import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.schemas.service import ServiceRead


class BookingBase(BaseModel):
    service_id: uuid.UUID
    scheduled_at: datetime
    notes: str | None = None


class BookingCreate(BookingBase):
    pass


class BookingRead(BookingBase):
    id: uuid.UUID
    user_id: uuid.UUID
    status: str
    total_amount: Decimal
    created_at: datetime
    service: ServiceRead | None = None

    model_config = ConfigDict(from_attributes=True)


class BookingUpdate(BaseModel):
    status: str | None = None
    scheduled_at: datetime | None = None
    notes: str | None = None
