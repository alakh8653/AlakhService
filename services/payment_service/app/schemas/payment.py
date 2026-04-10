from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, field_validator


class PaymentInitiate(BaseModel):
    booking_id: str
    payer_id: str
    payee_id: str
    amount_cents: int
    currency: str = "INR"
    payment_method: str
    idempotency_key: str

    @field_validator("amount_cents")
    @classmethod
    def validate_amount(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("amount_cents must be greater than 0")
        return v


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    booking_id: str
    payer_id: str
    payee_id: str
    amount_cents: int
    currency: str
    status: str
    payment_method: str
    gateway: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class RefundRequest(BaseModel):
    amount_cents: int
    reason: str

    @field_validator("amount_cents")
    @classmethod
    def validate_amount(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("amount_cents must be greater than 0")
        return v


class RefundResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    payment_id: str
    amount_cents: int
    reason: str
    status: str
    gateway_refund_id: Optional[str] = None
    created_at: datetime


class AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    owner_id: str
    owner_type: str
    balance_cents: int
    currency: str
    is_active: bool


class LedgerEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    account_id: str
    entry_type: str
    amount_cents: int
    currency: str
    description: str
    reference_id: Optional[str] = None
    running_balance: int
    created_at: datetime


class WebhookPayload(BaseModel):
    payload: dict
    signature: str


class TransactionHistoryResponse(BaseModel):
    items: List[LedgerEntryResponse]
    total: int
    page: int
    per_page: int
