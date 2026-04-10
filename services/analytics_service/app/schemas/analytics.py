from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict


class EventCreate(BaseModel):
    event_type: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None


class EventBatchCreate(BaseModel):
    events: List[EventCreate]


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    event_type: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    created_at: datetime


class MetricResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    metric_name: str
    dimension: Optional[str] = None
    value: float
    period_start: datetime
    period_end: datetime


class FunnelStep(BaseModel):
    event_type: str
    count: int


class FunnelAnalysisRequest(BaseModel):
    steps: List[str]  # List of event_types in sequence
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None


class FunnelAnalysisResponse(BaseModel):
    steps: List[FunnelStep]
    conversion_rates: List[float]


class CohortResponse(BaseModel):
    cohort_week: str
    user_count: int
    retained_week1: int
    retained_week2: int
