"""A shop's queue on the day: its settings, the durations it has learnt, its team's status, and an audit log."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text

from app.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class QueueSettings(Base):
    """How a shop runs its queue (defaults when it has no row)."""

    __tablename__ = "queue_settings"

    shop_id = Column(String, primary_key=True)
    # Added to every planned service length (0.1 = 10%).
    buffer_pct = Column(Float, default=0.0, server_default="0", nullable=False)
    # Weight of the newest actual duration in the learnt average.
    alpha = Column(Float, default=0.2, server_default="0.2", nullable=False)
    # How long after their time a customer may arrive before they can be marked a no-show.
    grace_minutes = Column(Integer, default=10, server_default="10", nullable=False)
    # Waiting this long moves a customer up one tier (walk-ins are then served like appointments).
    aging_minutes = Column(Integer, default=20, server_default="20", nullable=False)
    # Customers must check in on arrival; until they do, after the grace period they are out of the line,
    # and checking in late puts them in at the time they arrived.
    check_in_required = Column(Boolean, default=False, server_default="0", nullable=False)
    # At most this many customers may be made VIP in a day (keeps the line fair).
    vip_per_day = Column(Integer, default=5, server_default="5", nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class DurationStat(Base):
    """What a service actually takes at a shop (staff_id '' for the whole shop): an exponentially weighted
    mean and variance, in minutes, learnt from completed visits."""

    __tablename__ = "duration_stats"

    shop_id = Column(String, primary_key=True)
    service_id = Column(String, primary_key=True)
    staff_id = Column(String, primary_key=True, default="")
    mean = Column(Float, nullable=False)
    var = Column(Float, default=0.0, nullable=False)
    n = Column(Integer, default=0, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class WorkerStatus(Base):
    """A team member's status today, set by the shop: AVAILABLE, BREAK (until a time) or OFF."""

    __tablename__ = "worker_status"

    shop_id = Column(String, primary_key=True)
    staff_id = Column(String, primary_key=True)
    status = Column(String(10), nullable=False)
    until = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class QueueAudit(Base):
    """Who changed the line and how: reorder, VIP, walk-in, check-in, no-show, staff status."""

    __tablename__ = "queue_audit"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    shop_id = Column(String, nullable=False, index=True)
    booking_id = Column(String, nullable=True)
    action = Column(String(30), nullable=False)
    actor_id = Column(String, nullable=False)
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
