"""Signals reported by other platform services (booking, payment, queue, auth)."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.internal import require_internal
from app.database import get_db
from app.schemas.trust_risk import RiskSignalCreate, UserRiskProfileResponse
from app.services.trust_risk_service import trust_risk_service

router = APIRouter(prefix="/internal", dependencies=[Depends(require_internal)])


@router.post("/risk/{user_id}/signals", response_model=UserRiskProfileResponse)
async def report_signal(user_id: str, data: RiskSignalCreate, db: AsyncSession = Depends(get_db)):
    return await trust_risk_service.record_signal(db, user_id, data)
