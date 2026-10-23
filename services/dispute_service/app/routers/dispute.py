from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditReporter, Origin, get_audit_reporter, request_origin
from app.core.contact_filter import mask_contact
from app.core.exceptions import DisputeNotFoundError
from app.core.fsm import DisputeStatus
from app.core.settlement import NO_ACTION, SettlementClient, SettlementFailed, get_settlement_client
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


def _masked(text: Optional[str]) -> Optional[str]:
    return mask_contact(text).text if text else text


def _for_caller(dispute, caller: Caller) -> DisputeResponse:
    """The other party of a booking never reads contact details out of a dispute; admins see it as written."""
    out = DisputeResponse.model_validate(dispute)
    if caller.is_admin or dispute.raised_by == caller.user_id:
        return out
    return out.model_copy(update={"description": _masked(out.description)})


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
    return _for_caller(await _visible_dispute(db, dispute_id, caller, booking_check), caller)


async def _change_status(
    db: AsyncSession,
    dispute_id: str,
    to_status: DisputeStatus,
    resolution: Optional[str],
    caller: Caller,
    origin: Origin,
    audit: AuditReporter,
    background: BackgroundTasks,
    outcome: Optional[str] = None,
    amount_cents: Optional[int] = None,
):
    """Moves the dispute on as an admin and records who did it in admin_service's audit log."""
    try:
        from_status = (await dispute_service.get_dispute(db, dispute_id)).status
        if to_status == DisputeStatus.RESOLVED:
            dispute = await dispute_service.resolve(db, dispute_id, resolution, outcome, amount_cents)
        else:
            dispute = await dispute_service.transition(db, dispute_id, to_status)
    except DisputeNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()  # only a change that happened is reported
    new_values = {"status": DisputeStatus(dispute.status).value}
    if resolution is not None:
        new_values["resolution"] = resolution
    if outcome is not None:
        new_values["outcome"] = outcome
        if amount_cents is not None:
            new_values["refund_amount_cents"] = amount_cents
    background.add_task(
        audit.record,
        caller.user_id,
        "resolve_dispute" if to_status == DisputeStatus.RESOLVED else "update_dispute_status",
        "dispute",
        dispute.id,
        origin,
        old_values={"status": DisputeStatus(from_status).value},
        new_values=new_values,
    )
    return dispute


@router.post("/disputes/{dispute_id}/review", response_model=DisputeResponse)
async def review_dispute(
    dispute_id: str,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(require_admin),
    origin: Origin = Depends(request_origin),
    audit: AuditReporter = Depends(get_audit_reporter),
):
    return await _change_status(db, dispute_id, DisputeStatus.UNDER_REVIEW, None, caller, origin, audit, background)


@router.post("/disputes/{dispute_id}/escalate", response_model=DisputeResponse)
async def escalate_dispute(
    dispute_id: str,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(require_admin),
    origin: Origin = Depends(request_origin),
    audit: AuditReporter = Depends(get_audit_reporter),
):
    return await _change_status(db, dispute_id, DisputeStatus.ESCALATED, None, caller, origin, audit, background)


@router.post("/disputes/{dispute_id}/resolve", response_model=DisputeResponse)
async def resolve_dispute(
    dispute_id: str,
    data: DisputeResolve,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(require_admin),
    origin: Origin = Depends(request_origin),
    audit: AuditReporter = Depends(get_audit_reporter),
    settlement: SettlementClient = Depends(get_settlement_client),
):
    """Resolves the dispute and carries out its outcome first: the refund or release in payment_service,
    then the booking (REFUNDED, or COMPLETED again) in booking_service. If either fails nothing is
    resolved and the admin can try again; both sides apply an outcome once however often it is sent."""
    if data.outcome != NO_ACTION:
        try:
            dispute = await dispute_service.get_dispute(db, dispute_id)
        except DisputeNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        if not dispute_service.can_resolve(dispute):
            raise HTTPException(status_code=400, detail=f"Invalid transition: {dispute.status} -> RESOLVED")
        try:
            await settlement.settle_money(dispute.id, dispute.booking_id, data.outcome, data.amount_cents)
            await settlement.settle_booking(dispute.booking_id, data.outcome)
        except SettlementFailed as e:
            raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    return await _change_status(
        db,
        dispute_id,
        DisputeStatus.RESOLVED,
        data.resolution,
        caller,
        origin,
        audit,
        background,
        outcome=data.outcome,
        amount_cents=data.amount_cents,
    )


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
    messages = [DisputeMessageResponse.model_validate(m) for m in await dispute_service.get_messages(db, dispute_id)]
    if caller.is_admin:
        return messages
    return [
        m if m.author_id == caller.user_id else m.model_copy(update={"content": _masked(m.content)}) for m in messages
    ]
