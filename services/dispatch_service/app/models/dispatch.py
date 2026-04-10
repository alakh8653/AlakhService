import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Float
from sqlalchemy.sql import func
from app.database import Base


class DispatchJob(Base):
    __tablename__ = "dispatch_jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id = Column(String, nullable=False, index=True)
    provider_id = Column(String, nullable=False, index=True)
    status = Column(String, default="ASSIGNED", nullable=False)
    distance_km = Column(Float, nullable=True)
    assigned_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    estimated_arrival_at = Column(DateTime(timezone=True), nullable=True)


class AvailableProvider(Base):
    __tablename__ = "available_providers"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    provider_id = Column(String, nullable=False, unique=True, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    last_update = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    is_available = Column(Boolean, default=True, nullable=False)
