from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DisputeNotFoundError
from app.core.fsm import DisputeStatus
from app.database import get_db
from app.dependencies import BookingCheck, Caller, get_booking_check, require_admin, require_caller
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


async def _visible_dispute(db: AsyncSession, dispute_id: str, caller: Caller, booking_check: BookingCheck):
    """The dispute, if the caller raised it, is a party to its booking, or is an admin; else 404."""
    try:
        dispute = await dispute_service.get_dispute(db, dispute_id)
    except DisputeNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    if caller.is_admin or dispute.raised_by == caller.user_id:
        return dispute
    if await booking_check(dispute.booking_id, caller):
        return dispute
    raise HTTPException(status_code=404, detail="Dispute not found")


@router.post("/disputes", response_model=DisputeResponse, status_code=201)
async def create_dispute(
    data: DisputeCreate,
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(require_caller),
    booking_check: BookingCheck = Depends(get_booking_check),
):
    if not caller.is_admin:
        # Only someone involved in the booking can dispute it, and always in their own name.
        if not await booking_check(data.booking_id, caller):
            raise HTTPException(status_code=404, detail="Booking not found")
        data = data.model_copy(update={"raised_by": caller.user_id})
    elif not data.raised_by:
        data = data.model_copy(update={"raised_by": caller.user_id})
    return await dispute_service.create_dispute(db, data)


@router.get("/disputes", response_model=DisputeListResponse)
async def list_disputes(
    status: Optional[DisputeStatus] = None,
    booking_id: Optional[str] = None,
    raised_by: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(require_caller),
):
    if not caller.is_admin:
        raised_by = caller.user_id  # users list the disputes they raised
    disputes, total = await dispute_service.list_disputes(
        db, status=status, booking_id=booking_id, raised_by=raised_by, page=page, per_page=per_page
    )
    return DisputeListResponse(data=disputes, total=total, page=page, per_page=per_page)


@router.get("/disputes/{dispute_id}", response_model=DisputeResponse)
async def get_dispute(
    dispute_id: str,
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(require_caller),
    booking_check: BookingCheck = Depends(get_booking_check),
):
    return await _visible_dispute(db, dispute_id, caller, booking_check)


@router.post("/disputes/{dispute_id}/review", response_model=DisputeResponse, dependencies=[Depends(require_admin)])
async def review_dispute(dispute_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await dispute_service.transition(db, dispute_id, "UNDER_REVIEW")
    except DisputeNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/disputes/{dispute_id}/escalate", response_model=DisputeResponse, dependencies=[Depends(require_admin)])
async def escalate_dispute(dispute_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await dispute_service.transition(db, dispute_id, "ESCALATED")
    except DisputeNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/disputes/{dispute_id}/resolve", response_model=DisputeResponse, dependencies=[Depends(require_admin)])
async def resolve_dispute(dispute_id: str, data: DisputeResolve, db: AsyncSession = Depends(get_db)):
    try:
        return await dispute_service.resolve(db, dispute_id, data.resolution)
    except DisputeNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/disputes/{dispute_id}/messages", response_model=DisputeMessageResponse, status_code=201)
async def add_message(
    dispute_id: str,
    data: DisputeMessageCreate,
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(require_caller),
    booking_check: BookingCheck = Depends(get_booking_check),
):
    await _visible_dispute(db, dispute_id, caller, booking_check)
    # Messages are always posted in the caller's own name.
    data = data.model_copy(update={"author_id": caller.user_id})
    try:
        return await dispute_service.add_message(db, dispute_id, data)
    except DisputeNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/disputes/{dispute_id}/messages", response_model=List[DisputeMessageResponse])
async def get_messages(
    dispute_id: str,
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(require_caller),
    booking_check: BookingCheck = Depends(get_booking_check),
):
    await _visible_dispute(db, dispute_id, caller, booking_check)
    return await dispute_service.get_messages(db, dispute_id)
