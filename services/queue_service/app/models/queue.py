import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Float, Integer, ForeignKey
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
