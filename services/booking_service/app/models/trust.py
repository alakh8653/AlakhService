"""Customer trust: shared visit links and SOS alerts."""

import uuid

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, String, Text

from app.database import Base


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
