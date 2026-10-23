"""Calls from other platform services, authenticated with the shared INTERNAL_API_KEY.

These routes live outside /api/v1, which is all the gateway forwards, so only services on the
internal network reach them; the key keeps out anything else that can reach the port.
"""

import hmac
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.schemas.compliance import ConsentRecordCreate, ConsentRecordResponse
from app.services.compliance_service import compliance_service


def require_internal(x_internal_key: Optional[str] = Header(None)) -> None:
    if not settings.INTERNAL_API_KEY:
        raise HTTPException(status_code=503, detail="Internal API is not configured")
    if not x_internal_key or not hmac.compare_digest(x_internal_key, settings.INTERNAL_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid internal key")


router = APIRouter(dependencies=[Depends(require_internal)])


class InternalConsentCreate(BaseModel):
    """A consent given through another service, e.g. accepting the Terms when signing up.

    The IP address and user agent are the person's, passed on by the service they talked to.
    """

    user_id: str = Field(min_length=1, max_length=64)
    consent_type: str = Field(min_length=1, max_length=64)
    granted: bool = True
    version: str = Field("1.0", min_length=1, max_length=32)
    ip_address: Optional[str] = Field(None, max_length=64)
    user_agent: Optional[str] = Field(None, max_length=512)


@router.post("/internal/consent", response_model=ConsentRecordResponse, status_code=201)
async def record_consent(body: InternalConsentCreate, db: AsyncSession = Depends(get_db)):
    data = ConsentRecordCreate(
        user_id=body.user_id, consent_type=body.consent_type, granted=body.granted, version=body.version
    )
    return await compliance_service.record_consent(db, data, ip_address=body.ip_address, user_agent=body.user_agent)
