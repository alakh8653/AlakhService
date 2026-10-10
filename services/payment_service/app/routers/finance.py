from datetime import date, datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_admin
from app.schemas.finance import RevenueReport, SettlementList
from app.services import finance_service

router = APIRouter(dependencies=[Depends(require_admin)])

MAX_REPORT_DAYS = 366


@router.get("/finance/settlements", response_model=SettlementList)
async def list_settlements(
    status: Optional[Literal["CREATED", "HELD", "RELEASED", "REFUNDED"]] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    data, total = await finance_service.list_settlements(db, status=status, page=page, per_page=per_page)
    return SettlementList(data=data, total=total, page=page, per_page=per_page)


@router.get("/finance/revenue", response_model=RevenueReport)
async def revenue(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    currency: str = Query("INR", min_length=3, max_length=3),
    db: AsyncSession = Depends(get_db),
):
    date_to = date_to or datetime.now(timezone.utc).date()
    date_from = date_from or date_to - timedelta(days=29)
    if date_from > date_to:
        raise HTTPException(status_code=400, detail="date_from must not be after date_to")
    if (date_to - date_from).days >= MAX_REPORT_DAYS:
        raise HTTPException(status_code=400, detail=f"Report range is limited to {MAX_REPORT_DAYS} days")
    return await finance_service.revenue_report(db, date_from, date_to, currency.upper())
