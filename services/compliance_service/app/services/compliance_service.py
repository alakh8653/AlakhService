import uuid
from datetime import datetime, timezone
from typing import List, Optional, Union

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ErasureRequestNotFoundError, ExportRequestNotFoundError
from app.models.compliance import ConsentRecord, DataErasureRequest, DataExportRequest
from app.schemas.compliance import ConsentRecordCreate, DataErasureRequestCreate, DataExportRequestCreate

log = structlog.get_logger()

GdprRequest = Union[DataExportRequest, DataErasureRequest]


def k_anonymity_check(user_count: int, k: int = 5) -> bool:
    """Simple k-anonymity check: data must represent at least k users."""
    return user_count >= k


class ComplianceService:
    async def initiate_export(self, db: AsyncSession, data: DataExportRequestCreate) -> DataExportRequest:
        req = DataExportRequest(
            id=str(uuid.uuid4()),
            user_id=data.user_id,
            status="PENDING",
            requested_at=datetime.now(timezone.utc),
        )
        db.add(req)
        await db.flush()
        log.info("data_export_requested", user_id=data.user_id, request_id=req.id)
        return req

    async def get_export_status(self, db: AsyncSession, request_id: str) -> DataExportRequest:
        result = await db.execute(select(DataExportRequest).where(DataExportRequest.id == request_id))
        req = result.scalar_one_or_none()
        if not req:
            raise ExportRequestNotFoundError()
        return req

    async def complete_export(self, db: AsyncSession, request_id: str, export_url: str) -> DataExportRequest:
        req = await self.get_export_status(db, request_id)
        req.status = "COMPLETED"
        req.export_url = export_url
        req.completed_at = datetime.now(timezone.utc)
        await db.flush()
        return req

    async def request_erasure(self, db: AsyncSession, data: DataErasureRequestCreate) -> DataErasureRequest:
        req = DataErasureRequest(
            id=str(uuid.uuid4()),
            user_id=data.user_id,
            status="PENDING",
            reason=data.reason,
            requested_at=datetime.now(timezone.utc),
        )
        db.add(req)
        await db.flush()
        log.info("erasure_requested", user_id=data.user_id, request_id=req.id)
        return req

    async def get_erasure_request(self, db: AsyncSession, request_id: str) -> DataErasureRequest:
        result = await db.execute(select(DataErasureRequest).where(DataErasureRequest.id == request_id))
        req = result.scalar_one_or_none()
        if not req:
            raise ErasureRequestNotFoundError()
        return req

    async def list_requests(
        self,
        db: AsyncSession,
        model: type,
        user_id: Optional[str] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[GdprRequest]:
        query = select(model)
        if user_id:
            query = query.where(model.user_id == user_id)
        if status:
            query = query.where(model.status == status)
        # Oldest first: the statutory clock runs from the request date.
        query = query.order_by(model.requested_at.asc()).offset(skip).limit(limit)
        return list((await db.execute(query)).scalars().all())

    async def decide_request(
        self,
        db: AsyncSession,
        req: GdprRequest,
        status: str,
        admin_id: str,
        note: Optional[str] = None,
        export_url: Optional[str] = None,
    ) -> GdprRequest:
        req.status = status
        req.processed_by = admin_id
        req.resolution_note = note
        if export_url is not None:
            req.export_url = export_url
        req.completed_at = datetime.now(timezone.utc)
        await db.flush()
        log.info("gdpr_request_decided", request_id=req.id, status=status, admin_id=admin_id)
        return req

    async def record_consent(
        self,
        db: AsyncSession,
        data: ConsentRecordCreate,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ConsentRecord:
        record = ConsentRecord(
            id=str(uuid.uuid4()),
            user_id=data.user_id,
            consent_type=data.consent_type,
            granted=data.granted,
            ip_address=ip_address,
            user_agent=user_agent,
            version=data.version,
            created_at=datetime.now(timezone.utc),
        )
        db.add(record)
        await db.flush()
        log.info("consent_recorded", user_id=data.user_id, consent_type=data.consent_type, granted=data.granted)
        return record

    async def get_user_consents(self, db: AsyncSession, user_id: str) -> List[ConsentRecord]:
        result = await db.execute(
            select(ConsentRecord).where(ConsentRecord.user_id == user_id).order_by(ConsentRecord.created_at.desc())
        )
        return list(result.scalars().all())


compliance_service = ComplianceService()
