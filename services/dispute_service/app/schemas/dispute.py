from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class DisputeCreate(BaseModel):
    booking_id: str
    # Set from the caller's token; only admins may name someone else.
    raised_by: Optional[str] = None
    dispute_type: str = Field(min_length=1, max_length=50)
    description: str = Field(min_length=3, max_length=2000)
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


class DisputeListResponse(BaseModel):
    data: List[DisputeResponse]
    total: int
    page: int
    per_page: int


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
