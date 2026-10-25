from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UserRiskProfileNotFoundError
from app.database import get_db
from app.schemas.trust_risk import (
    RiskLevelsRequest,
    RiskSignalCreate,
    RiskSignalResponse,
    UserRiskProfileResponse,
)
from app.services.trust_risk_service import trust_risk_service

router = APIRouter()


@router.post("/risk/levels", response_model=List[UserRiskProfileResponse])
async def get_risk_levels(data: RiskLevelsRequest, db: AsyncSession = Depends(get_db)):
    # Only existing profiles: a user with no signals yet is simply absent (no profile is created here).
    return await trust_risk_service.get_profiles(db, data.user_ids)


@router.get("/risk/{user_id}", response_model=UserRiskProfileResponse)
async def get_risk_profile(user_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await trust_risk_service.get_or_create_profile(db, user_id)
    except UserRiskProfileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/risk/{user_id}/signal", response_model=UserRiskProfileResponse)
async def record_signal(user_id: str, data: RiskSignalCreate, db: AsyncSession = Depends(get_db)):
    return await trust_risk_service.record_signal(db, user_id, data)


@router.get("/risk/{user_id}/history", response_model=List[RiskSignalResponse])
async def get_signal_history(user_id: str, limit: int = Query(100, ge=1, le=500), db: AsyncSession = Depends(get_db)):
    return await trust_risk_service.get_signal_history(db, user_id, limit=limit)
