from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class LocationUpdate(BaseModel):
    provider_id: str
    latitude: float
    longitude: float
    accuracy: Optional[float] = None
    speed: Optional[float] = None
    heading: Optional[float] = None


class LocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    provider_id: str
    latitude: float
    longitude: float
    accuracy: Optional[float] = None
    speed: Optional[float] = None
    heading: Optional[float] = None
    timestamp: datetime


class GeofenceCreate(BaseModel):
    name: str
    center_lat: float
    center_lng: float
    radius_meters: float


class GeofenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    center_lat: float
    center_lng: float
    radius_meters: float
    is_active: bool


class GeofenceCheckResponse(BaseModel):
    geofence_id: str
    is_inside: bool
    latitude: float
    longitude: float
