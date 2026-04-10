import uuid
import json
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from collections import defaultdict
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from app.models.analytics import AnalyticsEvent, MetricAggregate
from app.schemas.analytics import EventBatchCreate, EventCreate, FunnelAnalysisRequest, FunnelAnalysisResponse, FunnelStep, CohortResponse

log = structlog.get_logger()


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

    async def get_metrics(self, db: AsyncSession, name: Optional[str] = None, from_date: Optional[datetime] = None, to_date: Optional[datetime] = None) -> List[MetricAggregate]:
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
            stmt = select(AnalyticsEvent).where(AnalyticsEvent.event_type == step_event, AnalyticsEvent.user_id.isnot(None))
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
        # Group users by signup week using created_at of first event
        result = await db.execute(
            select(AnalyticsEvent.user_id, AnalyticsEvent.created_at)
            .where(AnalyticsEvent.event_type == "signup", AnalyticsEvent.user_id.isnot(None))
        )
        signups = result.all()
        cohorts: dict[str, list[str]] = defaultdict(list)
        for user_id, created_at in signups:
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            week = created_at.strftime("%Y-W%W")
            cohorts[week].append(user_id)

        result2 = await db.execute(select(AnalyticsEvent).where(AnalyticsEvent.event_type == "active", AnalyticsEvent.user_id.isnot(None)))
        active_events = result2.scalars().all()

        cohort_responses = []
        for week, users in sorted(cohorts.items()):
            retained_w1 = sum(1 for u in users if any(e.user_id == u for e in active_events))
            cohort_responses.append(CohortResponse(
                cohort_week=week,
                user_count=len(users),
                retained_week1=retained_w1,
                retained_week2=0,
            ))

        return cohort_responses

    async def record_metric(self, db: AsyncSession, metric_name: str, value: float, dimension: Optional[str] = None) -> MetricAggregate:
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
