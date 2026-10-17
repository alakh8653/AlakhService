import json
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import AnalyticsEvent, MetricAggregate
from app.schemas.analytics import (
    CohortResponse,
    EventBatchCreate,
    FunnelAnalysisRequest,
    FunnelAnalysisResponse,
    FunnelStep,
)

log = structlog.get_logger()


def _aware(ts: datetime) -> datetime:
    # SQLite hands back naive datetimes; they are stored as UTC.
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


class AnalyticsService:
    async def ingest_events(self, db: AsyncSession, data: EventBatchCreate) -> List[AnalyticsEvent]:
        events = []
        for ev in data.events:
            event = AnalyticsEvent(
                id=str(uuid.uuid4()),
                event_type=ev.event_type,
                user_id=ev.user_id,
                session_id=ev.session_id,
                properties=json.dumps(ev.properties) if ev.properties else None,
                created_at=datetime.now(timezone.utc),
            )
            db.add(event)
            events.append(event)
        await db.flush()
        log.info("events_ingested", count=len(events))
        return events

    async def get_metrics(
        self,
        db: AsyncSession,
        name: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> List[MetricAggregate]:
        stmt = select(MetricAggregate)
        if name:
            stmt = stmt.where(MetricAggregate.metric_name == name)
        if from_date:
            stmt = stmt.where(MetricAggregate.period_start >= from_date)
        if to_date:
            stmt = stmt.where(MetricAggregate.period_end <= to_date)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def analyze_funnel(self, db: AsyncSession, data: FunnelAnalysisRequest) -> FunnelAnalysisResponse:
        if not data.steps:
            return FunnelAnalysisResponse(steps=[], conversion_rates=[])

        step_counts = []
        prev_users: Optional[set] = None

        for step_event in data.steps:
            stmt = select(AnalyticsEvent).where(
                AnalyticsEvent.event_type == step_event, AnalyticsEvent.user_id.isnot(None)
            )
            if data.from_date:
                stmt = stmt.where(AnalyticsEvent.created_at >= data.from_date)
            if data.to_date:
                stmt = stmt.where(AnalyticsEvent.created_at <= data.to_date)
            result = await db.execute(stmt)
            events = result.scalars().all()
            users_in_step = {e.user_id for e in events}

            if prev_users is not None:
                users_in_step = users_in_step & prev_users

            step_counts.append(FunnelStep(event_type=step_event, count=len(users_in_step)))
            prev_users = users_in_step

        conversion_rates = []
        for i in range(1, len(step_counts)):
            if step_counts[i - 1].count > 0:
                rate = step_counts[i].count / step_counts[i - 1].count
            else:
                rate = 0.0
            conversion_rates.append(rate)

        return FunnelAnalysisResponse(steps=step_counts, conversion_rates=conversion_rates)

    async def get_cohorts(self, db: AsyncSession) -> List[CohortResponse]:
        # Each user belongs to the week of their first signup event, however many they send.
        signups = (
            await db.execute(
                select(AnalyticsEvent.user_id, func.min(AnalyticsEvent.created_at))
                .where(AnalyticsEvent.event_type == "signup", AnalyticsEvent.user_id.isnot(None))
                .group_by(AnalyticsEvent.user_id)
            )
        ).all()
        signed_up_at = {user_id: _aware(created_at) for user_id, created_at in signups}

        active_at: dict[str, list[datetime]] = defaultdict(list)
        actives = await db.execute(
            select(AnalyticsEvent.user_id, AnalyticsEvent.created_at).where(
                AnalyticsEvent.event_type == "active", AnalyticsEvent.user_id.in_(list(signed_up_at))
            )
        )
        for user_id, created_at in actives:
            active_at[user_id].append(_aware(created_at))

        def active_between(user_id: str, start_day: int, end_day: int) -> bool:
            start = signed_up_at[user_id] + timedelta(days=start_day)
            end = signed_up_at[user_id] + timedelta(days=end_day)
            return any(start <= t < end for t in active_at[user_id])

        cohorts: dict[str, list[str]] = defaultdict(list)
        for user_id, created_at in signed_up_at.items():
            cohorts[created_at.strftime("%Y-W%W")].append(user_id)

        return [
            CohortResponse(
                cohort_week=week,
                user_count=len(users),
                retained_week1=sum(1 for u in users if active_between(u, 7, 14)),
                retained_week2=sum(1 for u in users if active_between(u, 14, 21)),
            )
            for week, users in sorted(cohorts.items())
        ]

    async def record_metric(
        self, db: AsyncSession, metric_name: str, value: float, dimension: Optional[str] = None
    ) -> MetricAggregate:
        now = datetime.now(timezone.utc)
        metric = MetricAggregate(
            id=str(uuid.uuid4()),
            metric_name=metric_name,
            dimension=dimension,
            value=value,
            period_start=now,
            period_end=now + timedelta(hours=1),
        )
        db.add(metric)
        await db.flush()
        return metric


analytics_service = AnalyticsService()
