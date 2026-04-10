from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class DataExportRequestCreate(BaseModel):
    user_id: str


class DataExportRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    status: str
    export_url: Optional[str] = None
    requested_at: datetime
    completed_at: Optional[datetime] = None


class DataErasureRequestCreate(BaseModel):
    user_id: str
    reason: Optional[str] = None


class DataErasureRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    status: str
    reason: Optional[str] = None
    requested_at: datetime
    completed_at: Optional[datetime] = None


class ConsentRecordCreate(BaseModel):
    user_id: str
    consent_type: str
    granted: bool
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    version: str = "1.0"


class ConsentRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    consent_type: str
    granted: bool
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    version: str
    created_at: datetime
