from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class RiskSignalCreate(BaseModel):
    signal_type: str  # e.g. "fraud_attempt", "successful_payment", "dispute_raised"
    value: float  # 1.0 = risk event, -1.0 = safe event (or use positive for risk intensity)
    is_risk_event: bool = True  # True = risk event, False = safe event


class UserRiskProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    risk_score: float
    risk_level: str
    risk_events: int
    safe_events: int
    ema_score: float
    last_updated: datetime


class RiskSignalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    signal_type: str
    value: float
    created_at: datetime
