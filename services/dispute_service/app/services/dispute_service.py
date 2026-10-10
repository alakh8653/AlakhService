import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DisputeNotFoundError
from app.core.fsm import DisputeFSM, DisputeStatus
from app.models.dispute import Dispute, DisputeMessage
from app.schemas.dispute import DisputeCreate, DisputeMessageCreate

log = structlog.get_logger()
_fsm = DisputeFSM()


class DisputeService:

    async def create_dispute(self, db: AsyncSession, data: DisputeCreate) -> Dispute:
        dispute = Dispute(
            id=str(uuid.uuid4()),
            booking_id=data.booking_id,
            raised_by=data.raised_by,
            dispute_type=data.dispute_type,
            description=data.description,
            status=DisputeStatus.OPEN,
            evidence_urls=json.dumps(data.evidence_urls) if data.evidence_urls else None,
            created_at=datetime.now(timezone.utc),
        )
        db.add(dispute)
        await db.flush()
        log.info("dispute_created", dispute_id=dispute.id, booking_id=data.booking_id)
        return dispute

    async def get_dispute(self, db: AsyncSession, dispute_id: str) -> Dispute:
        result = await db.execute(select(Dispute).where(Dispute.id == dispute_id))
        dispute = result.scalar_one_or_none()
        if not dispute:
            raise DisputeNotFoundError()
        return dispute

    async def list_disputes(
        self,
        db: AsyncSession,
        status: Optional[DisputeStatus] = None,
        booking_id: Optional[str] = None,
        raised_by: Optional[str] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> Tuple[List[Dispute], int]:
        """Newest first, with optional filters; returns (page of disputes, total matching)."""
        query = select(Dispute)
        if status is not None:
            query = query.where(Dispute.status == status)
        if booking_id:
            query = query.where(Dispute.booking_id == booking_id)
        if raised_by:
            query = query.where(Dispute.raised_by == raised_by)
        total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
        result = await db.execute(
            query.order_by(Dispute.created_at.desc(), Dispute.id).offset((page - 1) * per_page).limit(per_page)
        )
        return list(result.scalars().all()), total

    async def transition(self, db: AsyncSession, dispute_id: str, new_status: str) -> Dispute:
        dispute = await self.get_dispute(db, dispute_id)
        current = DisputeStatus(dispute.status)
        target = DisputeStatus(new_status)
        _fsm.transition(current, target)  # raises ValueError if invalid
        dispute.status = target
        await db.flush()
        log.info("dispute_transitioned", dispute_id=dispute_id, from_status=current, to_status=target)
        return dispute

    async def resolve(self, db: AsyncSession, dispute_id: str, resolution: str) -> Dispute:
        dispute = await self.get_dispute(db, dispute_id)
        current = DisputeStatus(dispute.status)
        _fsm.transition(current, DisputeStatus.RESOLVED)
        dispute.status = DisputeStatus.RESOLVED
        dispute.resolution = resolution
        dispute.resolved_at = datetime.now(timezone.utc)
        await db.flush()
        log.info("dispute_resolved", dispute_id=dispute_id)
        return dispute

    async def add_message(self, db: AsyncSession, dispute_id: str, data: DisputeMessageCreate) -> DisputeMessage:
        await self.get_dispute(db, dispute_id)  # verify exists
        msg = DisputeMessage(
            id=str(uuid.uuid4()),
            dispute_id=dispute_id,
            author_id=data.author_id,
            content=data.content,
            created_at=datetime.now(timezone.utc),
        )
        db.add(msg)
        await db.flush()
        return msg

    async def get_messages(self, db: AsyncSession, dispute_id: str) -> List[DisputeMessage]:
        result = await db.execute(select(DisputeMessage).where(DisputeMessage.dispute_id == dispute_id).order_by(DisputeMessage.created_at))
        return list(result.scalars().all())


dispute_service = DisputeService()
