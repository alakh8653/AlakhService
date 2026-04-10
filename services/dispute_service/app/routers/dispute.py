from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.database import get_db
from app.schemas.dispute import DisputeCreate, DisputeResponse, DisputeResolve, DisputeMessageCreate, DisputeMessageResponse
from app.services.dispute_service import dispute_service
from app.core.exceptions import DisputeNotFoundError, InvalidDisputeTransitionError

router = APIRouter()


@router.post("/disputes", response_model=DisputeResponse, status_code=201)
async def create_dispute(data: DisputeCreate, db: AsyncSession = Depends(get_db)):
    return await dispute_service.create_dispute(db, data)


@router.get("/disputes/{dispute_id}", response_model=DisputeResponse)
async def get_dispute(dispute_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await dispute_service.get_dispute(db, dispute_id)
    except DisputeNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/disputes/{dispute_id}/review", response_model=DisputeResponse)
async def review_dispute(dispute_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await dispute_service.transition(db, dispute_id, "UNDER_REVIEW")
    except DisputeNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/disputes/{dispute_id}/resolve", response_model=DisputeResponse)
async def resolve_dispute(dispute_id: str, data: DisputeResolve, db: AsyncSession = Depends(get_db)):
    try:
        return await dispute_service.resolve(db, dispute_id, data.resolution)
    except DisputeNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/disputes/{dispute_id}/messages", response_model=DisputeMessageResponse, status_code=201)
async def add_message(dispute_id: str, data: DisputeMessageCreate, db: AsyncSession = Depends(get_db)):
    try:
        return await dispute_service.add_message(db, dispute_id, data)
    except DisputeNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/disputes/{dispute_id}/messages", response_model=List[DisputeMessageResponse])
async def get_messages(dispute_id: str, db: AsyncSession = Depends(get_db)):
    return await dispute_service.get_messages(db, dispute_id)
