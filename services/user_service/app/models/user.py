import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Float, Text, Date
from sqlalchemy.sql import func
from app.database import Base


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, unique=True, nullable=False, index=True)
    full_name = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    bio = Column(Text, nullable=True)
    date_of_birth = Column(Date, nullable=True)
    gender = Column(String, nullable=True)
    language = Column(String, default="en", nullable=False)
    timezone = Column(String, default="UTC", nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)


class UserAddress(Base):
    __tablename__ = "user_addresses"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    label = Column(String, nullable=False)
    street = Column(String, nullable=False)
    city = Column(String, nullable=False)
    state = Column(String, nullable=False)
    postal_code = Column(String, nullable=False)
    country = Column(String, nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    is_default = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)


class UserPreferences(Base):
    __tablename__ = "user_preferences"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, unique=True, nullable=False, index=True)
    notifications_enabled = Column(Boolean, default=True, nullable=False)
    push_enabled = Column(Boolean, default=True, nullable=False)
    email_enabled = Column(Boolean, default=True, nullable=False)
    sms_enabled = Column(Boolean, default=True, nullable=False)
    language = Column(String, default="en", nullable=False)
    currency = Column(String, default="INR", nullable=False)
    theme = Column(String, default="light", nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)


class UserDevice(Base):
    __tablename__ = "user_devices"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    device_token = Column(String, nullable=False)
    platform = Column(String, nullable=False)  # ios, android, web
    device_id = Column(String, unique=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    last_seen = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
