from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


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
    resolution_note: Optional[str] = None


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
    resolution_note: Optional[str] = None


class ConsentRecordCreate(BaseModel):
    user_id: str
    consent_type: str
    granted: bool
    # The IP address and user agent are evidence, so they come from the request, never the body.
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


class GdprRequestDecision(BaseModel):
    status: Literal["COMPLETED", "REJECTED"]
    # Where the user downloads their data; required to complete an export.
    export_url: Optional[str] = Field(None, max_length=2000)
    note: Optional[str] = Field(None, max_length=2000)


class PendingGdprRequests(BaseModel):
    exports: List[DataExportRequestResponse]
    erasures: List[DataErasureRequestResponse]
