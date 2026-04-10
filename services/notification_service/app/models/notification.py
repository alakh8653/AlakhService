import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class NotificationTemplate(Base):
    __tablename__ = "notification_templates"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, unique=True, nullable=False, index=True)
    channel = Column(String, nullable=False)
    subject_template = Column(String, nullable=True)
    body_template = Column(String, nullable=False)
    variables = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    channel = Column(String, nullable=False)
    template_id = Column(String, ForeignKey("notification_templates.id", ondelete="SET NULL"), nullable=True)
    status = Column(String, default="PENDING", nullable=False)
    title = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    data = Column(Text, nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    failed_reason = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    channel = Column(String, nullable=False)
    is_enabled = Column(Boolean, default=True, nullable=False)
    quiet_hours_start = Column(Integer, nullable=True)
    quiet_hours_end = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)


class DeviceToken(Base):
    __tablename__ = "device_tokens"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    token = Column(String, unique=True, nullable=False)
    platform = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
