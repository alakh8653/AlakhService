from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.internal import require_internal
from app.database import get_db
from app.schemas.admin import AuditLogReport, AuditLogResponse
from app.services.admin_service import admin_service

router = APIRouter(dependencies=[Depends(require_internal)])


@router.post("/internal/audit-logs", response_model=AuditLogResponse, status_code=201)
async def record_audit_log(report: AuditLogReport, db: AsyncSession = Depends(get_db)):
    return await admin_service.record_report(db, report)
