from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime
from app.database import get_db
from app.schemas.analytics import EventBatchCreate, EventResponse, MetricResponse, FunnelAnalysisRequest, FunnelAnalysisResponse, CohortResponse
from app.services.analytics_service import analytics_service

router = APIRouter()


@router.post("/events", response_model=List[EventResponse], status_code=201)
async def ingest_events(data: EventBatchCreate, db: AsyncSession = Depends(get_db)):
    return await analytics_service.ingest_events(db, data)


@router.get("/metrics", response_model=List[MetricResponse])
async def get_metrics(
    name: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
):
    return await analytics_service.get_metrics(db, name=name, from_date=from_date, to_date=to_date)


@router.post("/funnels/analyze", response_model=FunnelAnalysisResponse)
async def analyze_funnel(data: FunnelAnalysisRequest, db: AsyncSession = Depends(get_db)):
    return await analytics_service.analyze_funnel(db, data)


@router.get("/cohorts", response_model=List[CohortResponse])
async def get_cohorts(db: AsyncSession = Depends(get_db)):
    return await analytics_service.get_cohorts(db)
