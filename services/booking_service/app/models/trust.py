"""Customer trust: extra charges the customer must approve, shared visit links, and SOS alerts."""

import json
import uuid

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String, Text, text

from app.database import Base

PENDING, APPROVED, DECLINED = "PENDING", "APPROVED", "DECLINED"


class ExtraChargeQuote(Base):
    """Extra work the shop or its provider wants to charge for: nothing is added until the customer approves."""

    __tablename__ = "extra_charge_quotes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id = Column(String, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(10), nullable=False, default=PENDING)
    # [{"description": ..., "amount_cents": ...}], descriptions with contact details hidden.
    items_json = Column("items", Text, nullable=False)
    total_cents = Column(Integer, nullable=False)
    note = Column(Text, nullable=True)
    requested_by = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    decided_by = Column(String, nullable=True)

    __table_args__ = (
        # One quote waits for an answer at a time: a second one is refused, even when two race.
        Index(
            "uq_extra_charge_quotes_one_pending",
            "booking_id",
            unique=True,
            postgresql_where=text("status = 'PENDING'"),
            sqlite_where=text("status = 'PENDING'"),
        ),
    )

    @property
    def items(self) -> list:
        return json.loads(self.items_json)


class BookingShare(Base):
    """A link the customer sends someone they trust to follow a visit: no login, no contact details."""

    __tablename__ = "booking_shares"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id = Column(String, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, unique=True)
    token = Column(String(64), nullable=False, unique=True)
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)


class SosAlert(Base):
    """A customer or provider asked for help during a booking; every admin is alerted."""

    __tablename__ = "sos_alerts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id = Column(String, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False)
    raised_by = Column(String, nullable=False)
    # customer or provider
    role = Column(String(10), nullable=False)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (Index("ix_sos_alerts_booking_created", "booking_id", "created_at"),)
