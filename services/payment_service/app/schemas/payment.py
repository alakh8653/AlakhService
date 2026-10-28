from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PaymentCheckout(BaseModel):
    """What a customer sends to pay for a booking; amount and parties come from the booking."""

    booking_id: str
    # "cash" is settled with the provider in person; the others go through Razorpay checkout.
    payment_method: Literal["upi", "card", "netbanking", "wallet", "cash"]
    idempotency_key: str = Field(min_length=8, max_length=128)


class TipCheckout(BaseModel):
    """A tip for the provider of one of your completed bookings, paid online."""

    booking_id: str
    amount_cents: int
    payment_method: Literal["upi", "card", "netbanking", "wallet"]
    idempotency_key: str = Field(min_length=8, max_length=128)


class PaymentInitiate(BaseModel):
    booking_id: str
    payer_id: str
    payee_id: str
    shop_id: Optional[str] = None
    amount_cents: int
    currency: str = "INR"
    payment_method: str
    idempotency_key: str
    purpose: Literal["BOOKING", "TIP"] = "BOOKING"
    # Stored with the payment (JSON), e.g. which provider a tip is for.
    metadata_json: Optional[str] = None

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
    shop_id: Optional[str] = None
    invoice_number: Optional[str] = None
    # BOOKING, or TIP for a tip added to a completed booking.
    purpose: str = "BOOKING"
    created_at: datetime
    updated_at: datetime


class RazorpayCheckout(BaseModel):
    """What the app passes to Razorpay's checkout to collect the payment."""

    gateway: Literal["razorpay"] = "razorpay"
    key_id: str
    order_id: str
    amount_cents: int
    currency: str


class PaymentCheckoutResponse(PaymentResponse):
    # Present while an online payment is waiting to be paid at the gateway.
    checkout: Optional[RazorpayCheckout] = None


class RazorpayVerification(BaseModel):
    """The fields Razorpay's checkout hands the app after a successful payment."""

    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


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


class TransactionHistoryResponse(BaseModel):
    items: List[LedgerEntryResponse]
    total: int
    page: int
    per_page: int
