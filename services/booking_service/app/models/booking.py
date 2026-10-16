import json
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.database import Base


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_number = Column(String, unique=True, nullable=False)
    customer_id = Column(String, nullable=False, index=True)
    provider_id = Column(String, nullable=True, index=True)
    service_id = Column(String, nullable=False)
    shop_id = Column(String, nullable=True, index=True)
    status = Column(String, default="PENDING", nullable=False)
    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    address_id = Column(String, nullable=True)
    # AT_SHOP, AT_HOME or PICKUP_DROP (see app.core.fsm).
    service_mode = Column(String(20), default="AT_SHOP", server_default="AT_SHOP", nullable=False)
    # For pickup & drop: what is being collected and what is wrong with it.
    item_description = Column(Text, nullable=True)
    # For pickup & drop: when the shop expects to have the item back with the customer.
    ready_by = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    total_amount = Column(Integer, nullable=False)  # in cents
    metadata_json = Column("metadata", Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)

    def _meta(self) -> dict:
        try:
            return json.loads(self.metadata_json) if self.metadata_json else {}
        except ValueError:
            return {}

    @property
    def service_mode_fee(self) -> int:
        return self._meta().get("service_mode_fee", 0)

    @property
    def coupon_code(self):
        return self._meta().get("coupon_code")

    @property
    def list_price(self) -> int:
        """The catalogue price before any coupon (total_amount is what the customer pays)."""
        return self._meta().get("list_price", self.total_amount)


class BookingStatusHistory(Base):
    __tablename__ = "booking_status_history"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id = Column(String, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True)
    from_status = Column(String, nullable=True)
    to_status = Column(String, nullable=False)
    changed_by = Column(String, nullable=False)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)


class BookingAssignment(Base):
    __tablename__ = "booking_assignments"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id = Column(String, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True)
    provider_id = Column(String, nullable=False)
    assigned_at = Column(DateTime(timezone=True), nullable=False)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    rejected_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)
