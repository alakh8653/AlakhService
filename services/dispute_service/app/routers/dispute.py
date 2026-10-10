from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DisputeNotFoundError
from app.core.fsm import DisputeStatus
from app.database import get_db
from app.schemas.dispute import (
    DisputeCreate,
    DisputeListResponse,
    DisputeMessageCreate,
    DisputeMessageResponse,
    DisputeResolve,
    DisputeResponse,
)
from app.services.dispute_service import dispute_service

router = APIRouter()


@router.post("/disputes", response_model=DisputeResponse, status_code=201)
async def create_dispute(data: DisputeCreate, db: AsyncSession = Depends(get_db)):
    return await dispute_service.create_dispute(db, data)


@router.get("/disputes", response_model=DisputeListResponse)
async def list_disputes(
    status: Optional[DisputeStatus] = None,
    booking_id: Optional[str] = None,
    raised_by: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    disputes, total = await dispute_service.list_disputes(
        db, status=status, booking_id=booking_id, raised_by=raised_by, page=page, per_page=per_page
    )
    return DisputeListResponse(data=disputes, total=total, page=page, per_page=per_page)


@router.get("/disputes/{dispute_id}", response_model=DisputeResponse)
async def get_dispute(dispute_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await dispute_service.get_dispute(db, dispute_id)
    except DisputeNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/disputes/{dispute_id}/review", response_model=DisputeResponse)
async def review_dispute(dispute_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await dispute_service.transition(db, dispute_id, "UNDER_REVIEW")
    except DisputeNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/disputes/{dispute_id}/escalate", response_model=DisputeResponse)
async def escalate_dispute(dispute_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await dispute_service.transition(db, dispute_id, "ESCALATED")
    except DisputeNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/disputes/{dispute_id}/resolve", response_model=DisputeResponse)
async def resolve_dispute(dispute_id: str, data: DisputeResolve, db: AsyncSession = Depends(get_db)):
    try:
        return await dispute_service.resolve(db, dispute_id, data.resolution)
    except DisputeNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/disputes/{dispute_id}/messages", response_model=DisputeMessageResponse, status_code=201)
async def add_message(dispute_id: str, data: DisputeMessageCreate, db: AsyncSession = Depends(get_db)):
    try:
        return await dispute_service.add_message(db, dispute_id, data)
    except DisputeNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/disputes/{dispute_id}/messages", response_model=List[DisputeMessageResponse])
async def get_messages(dispute_id: str, db: AsyncSession = Depends(get_db)):
    return await dispute_service.get_messages(db, dispute_id)
