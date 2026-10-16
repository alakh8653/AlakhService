import uuid

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.sql import func

from app.database import Base


class Queue(Base):
    __tablename__ = "queues"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    service_id = Column(String, nullable=False, index=True)
    max_capacity = Column(Integer, default=50, nullable=False)
    current_size = Column(Integer, default=0, nullable=False)
    is_accepting = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # How many customers are served at the same time (chairs / staff on this service).
    servers = Column(Integer, default=1, server_default="1", nullable=False)
    # Average minutes per customer: starts from the service's listed duration and then
    # follows the real time from "called" to "done" (see QueueService.complete).
    avg_service_minutes = Column(Float, default=5.0, server_default="5", nullable=False)
    # A called customer who has not shown up after this long is skipped as a no-show.
    no_show_grace_minutes = Column(Integer, default=10, server_default="10", nullable=False)
    # Customers are told "almost your turn" when this many or fewer people are ahead of them.
    notify_ahead = Column(Integer, default=2, server_default="2", nullable=False)


class QueueEntry(Base):
    __tablename__ = "queue_entries"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    queue_id = Column(String, ForeignKey("queues.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id = Column(String, nullable=False, index=True)
    service_id = Column(String, nullable=False)
    priority = Column(Integer, default=0, nullable=False)
    weight = Column(Float, default=1.0, nullable=False)
    position = Column(Integer, default=0, nullable=False)
    status = Column(String, default="WAITING", nullable=False)
    entered_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    estimated_wait_minutes = Column(Integer, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    called_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    # Whether the "almost your turn" notice went out, so it is sent once.
    notified_soon = Column(Boolean, default=False, server_default="false", nullable=False)
