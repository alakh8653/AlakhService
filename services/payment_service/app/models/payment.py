import uuid

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.sql import func

from app.database import Base

# What a payment is for: the booking itself, or a tip the customer adds once it is completed.
BOOKING, TIP = "BOOKING", "TIP"


class Account(Base):
    __tablename__ = "accounts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id = Column(String, nullable=False, index=True)
    owner_type = Column(String, nullable=False)  # user, provider, platform
    balance_cents = Column(Integer, default=0, nullable=False)
    currency = Column(String, default="INR", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = Column(String, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    entry_type = Column(String, nullable=False)  # DEBIT or CREDIT
    amount_cents = Column(Integer, nullable=False)
    currency = Column(String, nullable=False)
    description = Column(String, nullable=False)
    reference_id = Column(String, nullable=True)
    reference_type = Column(String, nullable=True)
    running_balance = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)


class Payment(Base):
    __tablename__ = "payments"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id = Column(String, nullable=False, index=True)
    payer_id = Column(String, nullable=False, index=True)
    payee_id = Column(String, nullable=False)
    # The booking's shop (payee_id is its owner); earnings and payouts are kept per shop.
    shop_id = Column(String, nullable=True, index=True)
    amount_cents = Column(Integer, nullable=False)
    currency = Column(String, default="INR", nullable=False)
    status = Column(String, default="PENDING", nullable=False)
    payment_method = Column(String, nullable=False)
    provider_payment_id = Column(String, nullable=True)
    provider_order_id = Column(String, nullable=True, index=True)
    gateway = Column(String, nullable=True)  # razorpay, cash
    # BOOKING or TIP: a booking is paid for once, and tipped at most once, each on its own.
    purpose = Column(String(10), nullable=False, default=BOOKING, server_default=BOOKING)
    idempotency_key = Column(String, unique=True, nullable=False)
    metadata_json = Column("metadata", Text, nullable=True)
    # Numbered when the payment completes, gap-free per financial year: ALK/2026-27/000123.
    invoice_number = Column(String, nullable=True)
    invoice_issued_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)

    # A booking is paid for (and tipped) once, even if two checkouts are confirmed at the same moment.
    __table_args__ = (
        Index(
            "uq_payments_booking_purpose_completed",
            "booking_id",
            "purpose",
            unique=True,
            sqlite_where=text("status = 'COMPLETED'"),
            postgresql_where=text("status = 'COMPLETED'"),
        ),
        UniqueConstraint("invoice_number", name="uq_payments_invoice_number"),
    )


class Escrow(Base):
    __tablename__ = "escrows"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    payment_id = Column(String, ForeignKey("payments.id", ondelete="CASCADE"), nullable=False, index=True)
    booking_id = Column(String, nullable=False)
    amount_cents = Column(Integer, nullable=False)
    currency = Column(String, nullable=False)
    status = Column(String, default="CREATED", nullable=False)
    held_at = Column(DateTime(timezone=True), nullable=False)
    released_at = Column(DateTime(timezone=True), nullable=True)


class Refund(Base):
    __tablename__ = "refunds"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    payment_id = Column(String, ForeignKey("payments.id", ondelete="CASCADE"), nullable=False, index=True)
    amount_cents = Column(Integer, nullable=False)
    reason = Column(String, nullable=False)
    status = Column(String, default="PENDING", nullable=False)
    gateway_refund_id = Column(String, nullable=True)
    # Set by automatic refunds (cancel:{booking_id}, dispute:{dispute_id}) so a retried call refunds once.
    idempotency_key = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_refunds_idempotency_key"),)


class CommissionRate(Base):
    """An admin's commission rate for one shop, or for every shop without its own (shop_id "*")."""

    __tablename__ = "commission_rates"

    shop_id = Column(String, primary_key=True)
    commission_percent = Column(Numeric(5, 2), nullable=False)
    updated_by = Column(String, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)


class InvoiceSequence(Base):
    """The last invoice number used in a series (one series per financial year)."""

    __tablename__ = "invoice_sequences"

    series = Column(String, primary_key=True)
    last_number = Column(Integer, nullable=False, default=0)


class ShopEarning(Base):
    """What one booking earned its shop, after the platform's commission and GST on that commission.

    SALE is the booking itself (one per booking); ADJUSTMENT corrects a SALE already paid out (a later
    refund), so the difference is netted against the shop's next payout. TIP is a tip the customer paid
    online for its provider: no commission or GST, all of it paid out (TIP_ADJUSTMENT corrects one already
    paid out).

    ONLINE: the platform collected the money and owes the shop ``net`` (payout_cents = net).
    CASH: the shop collected it and owes the platform commission + GST (payout_cents is negative).
    """

    __tablename__ = "shop_earnings"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id = Column(String, nullable=False, index=True)
    kind = Column(String(20), nullable=False, default="SALE")
    payment_id = Column(String, nullable=True)
    shop_id = Column(String, nullable=False, index=True)
    collection = Column(String(10), nullable=False)  # ONLINE or CASH
    currency = Column(String, nullable=False, default="INR")
    gross_cents = Column(Integer, nullable=False)
    commission_percent = Column(Numeric(5, 2), nullable=False)
    gst_percent = Column(Numeric(5, 2), nullable=False)
    commission_cents = Column(Integer, nullable=False)
    gst_cents = Column(Integer, nullable=False)
    net_cents = Column(Integer, nullable=False)
    payout_cents = Column(Integer, nullable=False)
    status = Column(String(10), nullable=False)  # HELD, READY, PAID, REFUNDED
    # TIP: the staff member who did the job; the shop passes the tip on to them in full.
    provider_id = Column(String, nullable=True)
    payout_id = Column(String, ForeignKey("payouts.id"), nullable=True, index=True)
    completed_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("booking_id", "kind", name="uq_shop_earnings_booking_kind"),)


class Payout(Base):
    """Money paid to a shop for a period, made by an admin batch and marked paid once transferred."""

    __tablename__ = "payouts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    batch_id = Column(String, nullable=False, index=True)
    shop_id = Column(String, nullable=False, index=True)
    period_from = Column(Date, nullable=True)
    period_to = Column(Date, nullable=False)
    amount_cents = Column(Integer, nullable=False)
    currency = Column(String, nullable=False, default="INR")
    status = Column(String(10), nullable=False, default="PENDING")  # PENDING, PAID
    paid_at = Column(DateTime(timezone=True), nullable=True)
    reference = Column(String, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
