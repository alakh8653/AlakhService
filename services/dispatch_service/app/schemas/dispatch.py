from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class ProviderInfo(BaseModel):
    provider_id: str
    latitude: float
    longitude: float


class AssignRequest(BaseModel):
    booking_id: str
    booking_lat: float
    booking_lon: float
    providers: List[ProviderInfo]


class AssignResponse(BaseModel):
    booking_id: str
    provider_id: str
    distance_km: float
    job_id: str


class ProviderLocationUpdate(BaseModel):
    provider_id: str
    latitude: float
    longitude: float
    is_available: bool = True


class AvailableProviderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    provider_id: str
    latitude: float
    longitude: float
    last_update: datetime
    is_available: bool


class DispatchJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    booking_id: str
    provider_id: str
    status: str
    distance_km: Optional[float] = None
    assigned_at: datetime
    estimated_arrival_at: Optional[datetime] = None
