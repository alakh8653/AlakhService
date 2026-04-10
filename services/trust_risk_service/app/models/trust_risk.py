import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, DateTime
from sqlalchemy.sql import func
from app.database import Base


class UserRiskProfile(Base):
    __tablename__ = "user_risk_profiles"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, unique=True, index=True)
    risk_score = Column(Float, default=0.1, nullable=False)
    risk_level = Column(String, default="LOW", nullable=False)
    risk_events = Column(Integer, default=0, nullable=False)
    safe_events = Column(Integer, default=0, nullable=False)
    ema_score = Column(Float, default=0.0, nullable=False)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class RiskSignal(Base):
    __tablename__ = "risk_signals"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    signal_type = Column(String, nullable=False)
    value = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
