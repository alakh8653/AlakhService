import uuid
from datetime import datetime, timezone
from typing import List
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.trust_risk import UserRiskProfile, RiskSignal
from app.schemas.trust_risk import RiskSignalCreate
from app.core.risk_engine import BayesianRiskScorer

log = structlog.get_logger()
_scorer = BayesianRiskScorer()


class TrustRiskService:

    async def get_or_create_profile(self, db: AsyncSession, user_id: str) -> UserRiskProfile:
        result = await db.execute(select(UserRiskProfile).where(UserRiskProfile.user_id == user_id))
        profile = result.scalar_one_or_none()
        if not profile:
            profile = UserRiskProfile(
                id=str(uuid.uuid4()),
                user_id=user_id,
                risk_score=_scorer.compute_score(0, 0, 0.0),
                risk_level=_scorer.risk_level(_scorer.compute_score(0, 0, 0.0)),
                risk_events=0,
                safe_events=0,
                ema_score=0.0,
                last_updated=datetime.now(timezone.utc),
            )
            db.add(profile)
            await db.flush()
        return profile

    async def record_signal(self, db: AsyncSession, user_id: str, data: RiskSignalCreate) -> UserRiskProfile:
        profile = await self.get_or_create_profile(db, user_id)

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
        result = await db.execute(select(RiskSignal).where(RiskSignal.user_id == user_id).order_by(RiskSignal.created_at.desc()))
        return list(result.scalars().all())


trust_risk_service = TrustRiskService()
