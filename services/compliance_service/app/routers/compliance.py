from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ErasureRequestNotFoundError, ExportRequestNotFoundError
from app.database import get_db
from app.dependencies import Caller, ensure_self_or_admin, require_admin, require_caller
from app.models.compliance import DataErasureRequest, DataExportRequest
from app.schemas.compliance import (
    ConsentRecordCreate,
    ConsentRecordResponse,
    DataErasureRequestCreate,
    DataErasureRequestResponse,
    DataExportRequestCreate,
    DataExportRequestResponse,
    GdprRequestDecision,
    PendingGdprRequests,
)
from app.services.compliance_service import compliance_service

router = APIRouter()


def own_user(user_id: Optional[str], caller: Caller) -> str:
    """The user whose requests to list: the caller, or anyone for an admin."""
    user_id = user_id or caller.user_id
    ensure_self_or_admin(user_id, caller)
    return user_id


@router.post("/gdpr/export", response_model=DataExportRequestResponse, status_code=201)
async def initiate_export(
    data: DataExportRequestCreate, db: AsyncSession = Depends(get_db), caller: Caller = Depends(require_caller)
):
    ensure_self_or_admin(data.user_id, caller)
    return await compliance_service.initiate_export(db, data)


@router.get("/gdpr/export", response_model=List[DataExportRequestResponse])
async def list_my_exports(
    user_id: Optional[str] = Query(None, description="Admins only; defaults to the caller"),
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(require_caller),
):
    return await compliance_service.list_requests(db, DataExportRequest, user_id=own_user(user_id, caller), limit=200)


@router.get("/gdpr/export/{request_id}", response_model=DataExportRequestResponse)
async def get_export_status(
    request_id: str, db: AsyncSession = Depends(get_db), caller: Caller = Depends(require_caller)
):
    try:
        export = await compliance_service.get_export_status(db, request_id)
    except ExportRequestNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    # Someone else's export (and its download link) is reported as missing.
    if not caller.is_admin and export.user_id != caller.user_id:
        raise HTTPException(status_code=404, detail="Export request not found")
    return export


@router.post("/gdpr/erasure", response_model=DataErasureRequestResponse, status_code=201)
async def request_erasure(
    data: DataErasureRequestCreate, db: AsyncSession = Depends(get_db), caller: Caller = Depends(require_caller)
):
    ensure_self_or_admin(data.user_id, caller)
    return await compliance_service.request_erasure(db, data)


@router.get("/gdpr/erasure", response_model=List[DataErasureRequestResponse])
async def list_my_erasures(
    user_id: Optional[str] = Query(None, description="Admins only; defaults to the caller"),
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(require_caller),
):
    return await compliance_service.list_requests(db, DataErasureRequest, user_id=own_user(user_id, caller), limit=200)


@router.get("/gdpr/erasure/{request_id}", response_model=DataErasureRequestResponse)
async def get_erasure_status(
    request_id: str, db: AsyncSession = Depends(get_db), caller: Caller = Depends(require_caller)
):
    try:
        erasure = await compliance_service.get_erasure_request(db, request_id)
    except ErasureRequestNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    if not caller.is_admin and erasure.user_id != caller.user_id:
        raise HTTPException(status_code=404, detail="Erasure request not found")
    return erasure


@router.get("/gdpr/admin/requests", response_model=PendingGdprRequests, dependencies=[Depends(require_admin)])
async def list_gdpr_requests(
    status: str = Query("PENDING", pattern="^(PENDING|COMPLETED|REJECTED)$"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """The queue operators work through; nothing processes these requests automatically yet."""
    return {
        "exports": await compliance_service.list_requests(db, DataExportRequest, status=status, skip=skip, limit=limit),
        "erasures": await compliance_service.list_requests(
            db, DataErasureRequest, status=status, skip=skip, limit=limit
        ),
    }


async def _decide(db: AsyncSession, req, decision: GdprRequestDecision, caller: Caller):
    # A decision is final: a completed erasure cannot be "un-rejected" and vice versa.
    if req.status != "PENDING":
        raise HTTPException(status_code=409, detail=f"Request is already {req.status}")
    return await compliance_service.decide_request(
        db, req, decision.status, caller.user_id, note=decision.note, export_url=decision.export_url
    )


@router.post("/gdpr/admin/export/{request_id}/decision", response_model=DataExportRequestResponse)
async def decide_export(
    request_id: str,
    decision: GdprRequestDecision,
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(require_admin),
):
    if decision.status == "COMPLETED" and not decision.export_url:
        raise HTTPException(status_code=422, detail="export_url is required to complete an export")
    try:
        req = await compliance_service.get_export_status(db, request_id)
    except ExportRequestNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return await _decide(db, req, decision, caller)


@router.post("/gdpr/admin/erasure/{request_id}/decision", response_model=DataErasureRequestResponse)
async def decide_erasure(
    request_id: str,
    decision: GdprRequestDecision,
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(require_admin),
):
    if decision.export_url:
        raise HTTPException(status_code=422, detail="export_url only applies to exports")
    try:
        req = await compliance_service.get_erasure_request(db, request_id)
    except ErasureRequestNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return await _decide(db, req, decision, caller)


def client_address(request: Request) -> Optional[str]:
    # The gateway overwrites X-Real-IP with the real peer, so it can be trusted over the socket address.
    return request.headers.get("x-real-ip") or (request.client.host if request.client else None)


@router.post("/consent", response_model=ConsentRecordResponse, status_code=201)
async def record_consent(
    data: ConsentRecordCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(require_caller),
):
    ensure_self_or_admin(data.user_id, caller)
    return await compliance_service.record_consent(
        db, data, ip_address=client_address(request), user_agent=request.headers.get("user-agent")
    )


@router.get("/consent/{user_id}", response_model=List[ConsentRecordResponse])
async def get_user_consents(user_id: str, db: AsyncSession = Depends(get_db), caller: Caller = Depends(require_caller)):
    ensure_self_or_admin(user_id, caller)
    return await compliance_service.get_user_consents(db, user_id)
