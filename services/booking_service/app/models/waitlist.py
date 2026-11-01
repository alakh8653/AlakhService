import uuid

from sqlalchemy import Column, Date, DateTime, Index, String, UniqueConstraint

from app.database import Base


class WaitlistEntry(Base):
    """A customer waiting for a time on [day] at a shop that was full; told once (notified_at)."""

    __tablename__ = "waitlist_entries"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    customer_id = Column(String, nullable=False, index=True)
    service_id = Column(String, nullable=False)
    shop_id = Column(String, nullable=False)
    day = Column(Date, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    notified_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("customer_id", "service_id", "day", name="uq_waitlist_customer_service_day"),
        Index("ix_waitlist_entries_shop_day", "shop_id", "day"),
    )
