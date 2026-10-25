import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.sql import func

from app.database import Base


class BookingMessage(Base):
    """One chat message between a booking's customer and its shop (owner or provider)."""

    __tablename__ = "booking_messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id = Column(String, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False)
    sender_id = Column(String, nullable=False, index=True)
    # customer, shop (its owner) or provider.
    sender_role = Column(String(20), nullable=False)
    # As delivered: contact details already replaced (app/core/contact_filter.py).
    body = Column(Text, nullable=False)
    # Contact details were found and hidden; what was written is kept for admins only.
    flagged = Column(Boolean, default=False, server_default="false", nullable=False)
    flag_reasons = Column(String(100), nullable=True)
    original_body = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    # When the other side first read it.
    read_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_booking_messages_booking_created", "booking_id", "created_at"),
        Index("ix_booking_messages_flagged_created", "flagged", "created_at"),
    )


class BookingCall(Base):
    """A masked call one party of a booking asked the telephony bridge to put through to the other."""

    __tablename__ = "booking_calls"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id = Column(String, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True)
    caller_id = Column(String, nullable=False, index=True)
    # Who was rung: customer, shop or provider. Never their number.
    callee_role = Column(String(20), nullable=False)
    provider = Column(String(20), nullable=False)
    provider_call_id = Column(String(100), nullable=True)
    status = Column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
