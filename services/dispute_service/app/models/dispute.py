import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Text
from sqlalchemy.sql import func
from app.database import Base


class Dispute(Base):
    __tablename__ = "disputes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id = Column(String, nullable=False, index=True)
    raised_by = Column(String, nullable=False)
    dispute_type = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String, default="OPEN", nullable=False)
    resolution = Column(Text, nullable=True)
    evidence_urls = Column(Text, nullable=True)  # JSON array as string
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)


class DisputeMessage(Base):
    __tablename__ = "dispute_messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    dispute_id = Column(String, nullable=False, index=True)
    author_id = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
