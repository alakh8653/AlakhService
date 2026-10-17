import uuid
from datetime import datetime, timezone
from typing import List

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.risk_engine import BayesianRiskScorer
from app.models.trust_risk import RiskSignal, UserRiskProfile
from app.schemas.trust_risk import RiskSignalCreate

log = structlog.get_logger()
_scorer = BayesianRiskScorer()


class TrustRiskService:
    async def get_or_create_profile(self, db: AsyncSession, user_id: str, lock: bool = False) -> UserRiskProfile:
        """The user's profile, created on first use; with `lock`, its row stays locked until the
        transaction ends, so concurrent signals for one user are applied one after another."""
        stmt = select(UserRiskProfile).where(UserRiskProfile.user_id == user_id)
        if lock:
            stmt = stmt.with_for_update()
        stmt = stmt.execution_options(populate_existing=True)
        profile = (await db.execute(stmt)).scalar_one_or_none()
        if profile is None:
            # Two first signals for a user may both get here; only one row is created and neither fails.
            insert = pg_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
            initial = _scorer.compute_score(0, 0, 0.0)
            await db.execute(
                insert(UserRiskProfile)
                .values(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    risk_score=initial,
                    risk_level=_scorer.risk_level(initial),
                    risk_events=0,
                    safe_events=0,
                    ema_score=0.0,
                    last_updated=datetime.now(timezone.utc),
                )
                .on_conflict_do_nothing(index_elements=[UserRiskProfile.user_id])
            )
            profile = (await db.execute(stmt)).scalar_one()
        return profile

    async def record_signal(self, db: AsyncSession, user_id: str, data: RiskSignalCreate) -> UserRiskProfile:
        # Locked: the counts and the moving average are read, updated and written back as one step.
        profile = await self.get_or_create_profile(db, user_id, lock=True)

        signal = RiskSignal(
            id=str(uuid.uuid4()),
            user_id=user_id,
            signal_type=data.signal_type,
            value=data.value,
            created_at=datetime.now(timezone.utc),
        )
        db.add(signal)

        if data.is_risk_event:
            profile.risk_events += 1
        else:
            profile.safe_events += 1

        new_signal_score = data.value if data.is_risk_event else 0.0
        profile.ema_score = _scorer.update_ema(profile.ema_score, new_signal_score)
        profile.risk_score = _scorer.compute_score(profile.risk_events, profile.safe_events, profile.ema_score)
        profile.risk_level = _scorer.risk_level(profile.risk_score)
        profile.last_updated = datetime.now(timezone.utc)

        await db.flush()
        log.info("risk_signal_recorded", user_id=user_id, signal_type=data.signal_type, new_score=profile.risk_score)
        return profile

    async def get_signal_history(self, db: AsyncSession, user_id: str) -> List[RiskSignal]:
        result = await db.execute(
            select(RiskSignal).where(RiskSignal.user_id == user_id).order_by(RiskSignal.created_at.desc())
        )
        return list(result.scalars().all())


trust_risk_service = TrustRiskService()
