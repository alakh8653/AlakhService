import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


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
    amount_cents = Column(Integer, nullable=False)
    currency = Column(String, default="INR", nullable=False)
    status = Column(String, default="PENDING", nullable=False)
    payment_method = Column(String, nullable=False)
    provider_payment_id = Column(String, nullable=True)
    gateway = Column(String, nullable=True)  # razorpay, stripe
    idempotency_key = Column(String, unique=True, nullable=False)
    metadata_json = Column("metadata", Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)


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
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
