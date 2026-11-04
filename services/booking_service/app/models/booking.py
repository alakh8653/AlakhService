import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.sql import func

from app.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


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
    # Of total_amount, what the customer agreed to pay on top after the provider saw the job.
    extra_amount = Column(Integer, default=0, server_default="0", nullable=False)
    # The extra charge waiting for the customer's answer, with its reason's contact details hidden.
    pending_extra_id = Column(String, nullable=True)
    pending_extra_amount = Column(Integer, nullable=True)
    pending_extra_reason = Column(Text, nullable=True)
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
    # When the customer was asked whether they want to book this service again (once per visit).
    rebook_reminder_sent_at = Column(DateTime(timezone=True), nullable=True)
    # On the day: when the customer was told their turn is near, and that the shop is running late (once each).
    turn_soon_sent_at = Column(DateTime(timezone=True), nullable=True)
    running_late_sent_at = Column(DateTime(timezone=True), nullable=True)
    # The live queue (app/core/live_queue.py). BOOKED ahead, or a WALK_IN who joined the line on the day.
    source = Column(String(10), default="BOOKED", server_default="BOOKED", nullable=False)
    # 0 VIP, 1 appointment, 2 walk-in: who goes first when several are ready.
    priority = Column(Integer, default=1, server_default="1", nullable=False)
    checked_in_at = Column(DateTime(timezone=True), nullable=True)
    # Set when the shop moves people in the line by hand; lower goes first.
    queue_rank = Column(Float, nullable=True)
    # Who serves them (a team member's id) and when it began, set when the service starts.
    served_by_staff_id = Column(String, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    # A walk-in without an account: the name the shop calls out.
    walk_in_name = Column(String(80), nullable=True)
    # What the customer was last told about their place (app/core/queue_notify.py), as JSON.
    queue_notice_state = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    # Stamped by the app on every update, never left to the database: a server-side value would expire the
    # attribute, and reading it back later (building the response) fails outside the async session.
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("customer_id", "idempotency_key", name="uq_bookings_customer_idempotency_key"),
        # A shop's bookings by time (availability and the live queue read them this way).
        Index("ix_bookings_shop_scheduled", "shop_id", "scheduled_at"),
        # A team member serves one customer at a time: a second start for them fails (no double booking).
        Index(
            "uq_bookings_one_in_service_per_staff",
            "shop_id",
            "served_by_staff_id",
            unique=True,
            postgresql_where=text("status = 'IN_PROGRESS' AND served_by_staff_id IS NOT NULL"),
            sqlite_where=text("status = 'IN_PROGRESS' AND served_by_staff_id IS NOT NULL"),
        ),
    )

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
    def preferred_staff_id(self):
        """The staff member the customer asked for, if anyone."""
        return self._meta().get("preferred_staff_id")

    @property
    def preferred_staff_name(self):
        return self._meta().get("preferred_staff_name")

    @property
    def package_purchase_id(self):
        """The prepaid package this booking is a visit of, if any."""
        return self._meta().get("package_purchase_id")

    @property
    def points_discount(self) -> int:
        """What the customer's loyalty points paid (the platform pays it to the shop)."""
        return self._meta().get("points_discount", 0)

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


class BookingExtraCharge(Base):
    """What a provider asked for on top of the price, and the customer's answer. See routers/extra_charges.py."""

    __tablename__ = "booking_extra_charges"

    id = Column(String, primary_key=True)
    booking_id = Column(String, ForeignKey("bookings.id"), nullable=False, index=True)
    amount_cents = Column(Integer, nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(String(12), nullable=False)  # PENDING, APPROVED, DECLINED, WITHDRAWN, EXPIRED
    requested_by = Column(String, nullable=False)
    decided_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    decided_at = Column(DateTime(timezone=True), nullable=True)


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
