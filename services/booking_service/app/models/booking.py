import json
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
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
    # From the Idempotency-Key header: a retry of the same request finds this booking instead of making
    # another. Unique per customer, so of two requests racing with one key exactly one can insert.
    idempotency_key = Column(String(128), nullable=True)
    # Short hash of the request that made the booking: the same key with a different request is refused.
    request_hash = Column(String(32), nullable=True)
    # How its payment stands, as payment_service reports it: UNPAID, PAID, REFUNDED or PARTIALLY_REFUNDED.
    payment_status = Column(String(20), default="UNPAID", server_default="UNPAID", nullable=False)
    # Set when the reminder worker has sent each reminder, so each goes out once across replicas.
    reminder_24h_sent_at = Column(DateTime(timezone=True), nullable=True)
    reminder_1h_sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("customer_id", "idempotency_key", name="uq_bookings_customer_idempotency_key"),)

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
    def reschedule_count(self) -> int:
        """How many times the customer has moved the booking to another time."""
        return self._meta().get("reschedule_count", 0)

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


class PaymentOutbox(Base):
    """Something payment_service must hear about a booking (completed, cancelled, disputed).

    Written in the same transaction as the booking change, so it is never lost; delivered right after
    the change and retried by the background worker until payment_service accepts it. payment_service
    handles each of these idempotently, so delivering one twice is harmless.
    """

    __tablename__ = "payment_outbox"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id = Column(String, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(String(20), nullable=False)
    payload = Column(Text, nullable=False)
    attempts = Column(Integer, default=0, server_default="0", nullable=False)
    next_attempt_at = Column(DateTime(timezone=True), nullable=False, index=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("booking_id", "kind", name="uq_payment_outbox_booking_kind"),)
