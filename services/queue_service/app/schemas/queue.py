from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class QueueCreate(BaseModel):
    service_id: str
    max_capacity: int = 50


class QueueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    service_id: str
    max_capacity: int
    current_size: int
    is_accepting: bool
    created_at: datetime


class QueueJoinRequest(BaseModel):
    customer_id: str
    service_id: str
    priority: int = 0
    weight: float = 1.0


class QueueEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    queue_id: str
    customer_id: str
    service_id: str
    priority: int
    weight: float
    position: int
    status: str
    entered_at: datetime
    estimated_wait_minutes: Optional[int] = None
    expires_at: Optional[datetime] = None


class QueuePositionResponse(BaseModel):
    customer_id: str
    queue_id: str
    position: int
    estimated_wait_minutes: Optional[int] = None
