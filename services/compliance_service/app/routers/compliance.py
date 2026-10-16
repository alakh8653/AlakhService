from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ExportRequestNotFoundError
from app.database import get_db
from app.dependencies import Caller, ensure_self_or_admin, require_caller
from app.schemas.compliance import (
    ConsentRecordCreate,
    ConsentRecordResponse,
    DataErasureRequestCreate,
    DataErasureRequestResponse,
    DataExportRequestCreate,
    DataExportRequestResponse,
)
from app.services.compliance_service import compliance_service

router = APIRouter()


@router.post("/gdpr/export", response_model=DataExportRequestResponse, status_code=201)
async def initiate_export(
    data: DataExportRequestCreate, db: AsyncSession = Depends(get_db), caller: Caller = Depends(require_caller)
):
    ensure_self_or_admin(data.user_id, caller)
    return await compliance_service.initiate_export(db, data)


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


@router.post("/consent", response_model=ConsentRecordResponse, status_code=201)
async def record_consent(
    data: ConsentRecordCreate, db: AsyncSession = Depends(get_db), caller: Caller = Depends(require_caller)
):
    ensure_self_or_admin(data.user_id, caller)
    return await compliance_service.record_consent(db, data)


@router.get("/consent/{user_id}", response_model=List[ConsentRecordResponse])
async def get_user_consents(user_id: str, db: AsyncSession = Depends(get_db), caller: Caller = Depends(require_caller)):
    ensure_self_or_admin(user_id, caller)
    return await compliance_service.get_user_consents(db, user_id)
