from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class DisputeCreate(BaseModel):
    booking_id: str
    raised_by: str
    dispute_type: str
    description: str
    evidence_urls: Optional[List[str]] = None


class DisputeResolve(BaseModel):
    resolution: str


class DisputeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    booking_id: str
    raised_by: str
    dispute_type: str
    description: str
    status: str
    resolution: Optional[str] = None
    evidence_urls: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None


class DisputeMessageCreate(BaseModel):
    author_id: str
    content: str


class DisputeMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    dispute_id: str
    author_id: str
    content: str
    created_at: datetime
