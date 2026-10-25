from datetime import datetime
from typing import List

from pydantic import BaseModel, ConfigDict, Field


class RiskSignalCreate(BaseModel):
    signal_type: str = Field(min_length=1, max_length=50)  # e.g. "late_cancellation", "payment_completed"
    # Risk intensity for a risk event; a safe event only counts towards the safe side (send 0.0).
    value: float = Field(ge=0.0, le=1.0)
    is_risk_event: bool = True  # True = risk event, False = safe event


class RiskLevelsRequest(BaseModel):
    user_ids: List[str] = Field(max_length=200)


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
