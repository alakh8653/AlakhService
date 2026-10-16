from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import Caller, require_admin, require_caller
from app.schemas.analytics import (
    CohortResponse,
    EventBatchCreate,
    EventResponse,
    FunnelAnalysisRequest,
    FunnelAnalysisResponse,
    MetricResponse,
)
from app.services.analytics_service import analytics_service

router = APIRouter()


@router.post("/events", response_model=List[EventResponse], status_code=201)
async def ingest_events(
    data: EventBatchCreate, db: AsyncSession = Depends(get_db), caller: Caller = Depends(require_caller)
):
    # Users record events as themselves; only admins (e.g. backfills) may attribute them to others.
    if not caller.is_admin:
        data = EventBatchCreate(events=[e.model_copy(update={"user_id": caller.user_id}) for e in data.events])
    return await analytics_service.ingest_events(db, data)


@router.get("/metrics", response_model=List[MetricResponse], dependencies=[Depends(require_admin)])
async def get_metrics(
    name: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
):
    return await analytics_service.get_metrics(db, name=name, from_date=from_date, to_date=to_date)


@router.post("/funnels/analyze", response_model=FunnelAnalysisResponse, dependencies=[Depends(require_admin)])
async def analyze_funnel(data: FunnelAnalysisRequest, db: AsyncSession = Depends(get_db)):
    return await analytics_service.analyze_funnel(db, data)


@router.get("/cohorts", response_model=List[CohortResponse], dependencies=[Depends(require_admin)])
async def get_cohorts(db: AsyncSession = Depends(get_db)):
    return await analytics_service.get_cohorts(db)
