import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class PaymentBase(BaseModel):
    booking_id: uuid.UUID
    amount: Decimal
    currency: str = "INR"


class PaymentInitiate(BaseModel):
    booking_id: uuid.UUID


class PaymentVerify(BaseModel):
    gateway_order_id: str
    gateway_payment_id: str
    gateway_signature: str


class PaymentRead(BaseModel):
    id: uuid.UUID
    booking_id: uuid.UUID
    amount: Decimal
    currency: str
    status: str
    payment_gateway: str
    gateway_order_id: str | None = None
    gateway_payment_id: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
