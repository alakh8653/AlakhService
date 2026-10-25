from datetime import datetime
from typing import Annotated, List, Optional

from pydantic import BaseModel, ConfigDict, Field

# A position on Earth; anything else is a client bug or someone gaming the nearest-provider match.
Latitude = Annotated[float, Field(ge=-90, le=90)]
Longitude = Annotated[float, Field(ge=-180, le=180)]


class ProviderInfo(BaseModel):
    provider_id: str
    latitude: Latitude
    longitude: Longitude


class AssignRequest(BaseModel):
    booking_id: str
    booking_lat: Latitude
    booking_lon: Longitude
    providers: List[ProviderInfo]


class AssignResponse(BaseModel):
    booking_id: str
    provider_id: str
    distance_km: float
    job_id: str


class ProviderLocationUpdate(BaseModel):
    provider_id: str
    latitude: Latitude
    longitude: Longitude
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
