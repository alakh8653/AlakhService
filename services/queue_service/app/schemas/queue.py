from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class QueueCreate(BaseModel):
    service_id: str
    max_capacity: int = Field(50, ge=1, le=500)
    # Staff serving this queue at once, and minutes per customer (e.g. the service's listed duration).
    servers: int = Field(1, ge=1, le=50)
    avg_service_minutes: float = Field(5.0, ge=1, le=480)
    no_show_grace_minutes: int = Field(10, ge=1, le=120)
    notify_ahead: int = Field(2, ge=0, le=20)


class QueueUpdate(BaseModel):
    is_accepting: Optional[bool] = None
    servers: Optional[int] = Field(None, ge=1, le=50)
    avg_service_minutes: Optional[float] = Field(None, ge=1, le=480)
    no_show_grace_minutes: Optional[int] = Field(None, ge=1, le=120)
    notify_ahead: Optional[int] = Field(None, ge=0, le=20)


class QueueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    service_id: str
    max_capacity: int
    current_size: int
    is_accepting: bool
    created_at: datetime
    servers: int
    avg_service_minutes: float
    no_show_grace_minutes: int
    notify_ahead: int


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
    # What the shop calls the customer ("Ravi S."); never their phone, email or full name.
    customer_display_name: str = "Customer"
    service_id: str
    priority: int
    weight: float
    position: int
    status: str
    entered_at: datetime
    estimated_wait_minutes: Optional[int] = None
    expires_at: Optional[datetime] = None
    called_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class QueuePositionResponse(BaseModel):
    customer_id: str
    queue_id: str
    entry_id: str
    # WAITING, or CALLED once it is the customer's turn (position 0).
    status: str
    position: int
    people_ahead: int
    estimated_wait_minutes: Optional[int] = None
    # When the customer should expect to be called; a clock time is easier to plan around than minutes.
    estimated_call_at: Optional[datetime] = None
