import uuid
from datetime import datetime, timezone
from typing import List
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.compliance import DataExportRequest, ConsentRecord, DataErasureRequest
from app.schemas.compliance import DataExportRequestCreate, DataErasureRequestCreate, ConsentRecordCreate
from app.core.exceptions import ExportRequestNotFoundError

log = structlog.get_logger()


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

    async def record_consent(self, db: AsyncSession, data: ConsentRecordCreate) -> ConsentRecord:
        record = ConsentRecord(
            id=str(uuid.uuid4()),
            user_id=data.user_id,
            consent_type=data.consent_type,
            granted=data.granted,
            ip_address=data.ip_address,
            user_agent=data.user_agent,
            version=data.version,
            created_at=datetime.now(timezone.utc),
        )
        db.add(record)
        await db.flush()
        log.info("consent_recorded", user_id=data.user_id, consent_type=data.consent_type, granted=data.granted)
        return record

    async def get_user_consents(self, db: AsyncSession, user_id: str) -> List[ConsentRecord]:
        result = await db.execute(
            select(ConsentRecord)
            .where(ConsentRecord.user_id == user_id)
            .order_by(ConsentRecord.created_at.desc())
        )
        return list(result.scalars().all())


compliance_service = ComplianceService()
