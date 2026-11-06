"""A shop's profit and loss report, the expenses and income its owner writes down, and where reports go."""

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.money import IST, rupees
from app.core.peers import ShopDirectory, get_shop_directory
from app.core.reports import ReportSender, get_report_sender, send_report
from app.database import get_db
from app.dependencies import OwnerLookup, get_current_user, get_shop_owner_lookup
from app.models.payment import ShopCashEntry
from app.routers.money import _require_shop_access
from app.services import report_service

router = APIRouter()

PeriodParam = Literal["daily", "weekly", "monthly", "yearly"]
# The biggest single entry: a typing slip of a few zeros should not wreck a year's figures.
MAX_ENTRY_RUPEES = 10_000_000
ENTRY_CATEGORIES = (
    "MATERIALS",
    "SPARE_PARTS",
    "TRAVEL",
    "RENT",
    "STAFF",
    "TOOLS",
    "BILLS",
    "MARKETING",
    "OTHER",
    "OUTSIDE_WORK",
)


class CashEntryIn(BaseModel):
    kind: Literal["EXPENSE", "INCOME"]
    category: Literal[ENTRY_CATEGORIES]  # type: ignore[valid-type]
    amount: float = Field(gt=0, le=MAX_ENTRY_RUPEES)
    on_date: Optional[date] = None
    note: Optional[str] = Field(default=None, max_length=200)


class CashEntryOut(BaseModel):
    id: str
    kind: str
    category: str
    amount: float
    on_date: date
    note: Optional[str] = None


class ReportSettings(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    daily: bool = True
    weekly: bool = True
    monthly: bool = True
    yearly: bool = True
    email: bool = True
    whatsapp: bool = False


def _today() -> date:
    return datetime.now(IST).date()


def _entry_out(e: ShopCashEntry) -> CashEntryOut:
    return CashEntryOut(
        id=e.id, kind=e.kind, category=e.category, amount=rupees(e.amount_cents), on_date=e.on_date, note=e.note
    )


@router.get("/payments/shops/{shop_id}/report")
async def report(
    shop_id: str,
    period: PeriodParam = "monthly",
    on: Optional[date] = None,
    db: AsyncSession = Depends(get_db, scope="function"),
    current_user: dict = Depends(get_current_user),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
):
    await _require_shop_access(shop_id, current_user, lookup_owner)
    return await report_service.build(db, shop_id, period, on or _today())


@router.get("/payments/shops/{shop_id}/report.csv")
async def report_csv(
    shop_id: str,
    period: PeriodParam = "monthly",
    on: Optional[date] = None,
    db: AsyncSession = Depends(get_db, scope="function"),
    current_user: dict = Depends(get_current_user),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
):
    await _require_shop_access(shop_id, current_user, lookup_owner)
    built = await report_service.build(db, shop_id, period, on or _today())
    return Response(
        content=report_service.to_csv(built),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="report-{period}-{built["from"]}.csv"'},
    )


@router.post("/payments/shops/{shop_id}/report/send")
async def send_now(
    shop_id: str,
    period: PeriodParam = "monthly",
    db: AsyncSession = Depends(get_db, scope="function"),
    current_user: dict = Depends(get_current_user),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
    shops: ShopDirectory = Depends(get_shop_directory),
    sender: ReportSender = Depends(get_report_sender),
):
    """Sends this period's report to the owner now, through the channels they chose. Says where it went."""
    await _require_shop_access(shop_id, current_user, lookup_owner)
    built = await report_service.build(db, shop_id, period, _today())
    prefs = await report_service.preference(db, shop_id)
    used = (prefs.sent_count or 0) if prefs.sent_on == _today() else 0
    if used >= settings.REPORT_SENDS_PER_DAY:
        raise HTTPException(status_code=429, detail="You have sent this report enough times today. Try again tomorrow.")
    sent = await send_report(shops, sender, shop_id, built, prefs)
    if sent is None:
        raise HTTPException(status_code=503, detail="The report could not be sent just now. Please try again.")
    prefs.sent_on = _today()
    prefs.sent_count = used + 1
    db.add(prefs)
    await db.flush()
    return {"sent_to": sent}


@router.get("/payments/shops/{shop_id}/cash-entries", response_model=List[CashEntryOut])
async def list_cash_entries(
    shop_id: str,
    date_from: Optional[date] = Query(None, alias="from"),
    date_to: Optional[date] = Query(None, alias="to"),
    db: AsyncSession = Depends(get_db, scope="function"),
    current_user: dict = Depends(get_current_user),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
):
    await _require_shop_access(shop_id, current_user, lookup_owner)
    date_to = date_to or _today()
    date_from = date_from or date_to - timedelta(days=30)
    return [_entry_out(e) for e in await report_service.list_entries(db, shop_id, date_from, date_to)]


@router.post("/payments/shops/{shop_id}/cash-entries", response_model=CashEntryOut, status_code=201)
async def add_cash_entry(
    shop_id: str,
    body: CashEntryIn,
    db: AsyncSession = Depends(get_db, scope="function"),
    current_user: dict = Depends(get_current_user),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
):
    await _require_shop_access(shop_id, current_user, lookup_owner)
    on_date = body.on_date or _today()
    if on_date > _today():
        raise HTTPException(status_code=422, detail="The date cannot be in the future")
    entry = ShopCashEntry(
        id=str(uuid.uuid4()),
        shop_id=shop_id,
        kind=body.kind,
        category=body.category,
        amount_cents=round(body.amount * 100),
        on_date=on_date,
        note=(body.note or "").strip() or None,
        created_by=current_user["sub"],
        created_at=datetime.now(timezone.utc),
    )
    db.add(entry)
    await db.flush()
    return _entry_out(entry)


@router.delete("/payments/shops/{shop_id}/cash-entries/{entry_id}", status_code=204)
async def delete_cash_entry(
    shop_id: str,
    entry_id: str,
    db: AsyncSession = Depends(get_db, scope="function"),
    current_user: dict = Depends(get_current_user),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
):
    await _require_shop_access(shop_id, current_user, lookup_owner)
    entry = await db.get(ShopCashEntry, entry_id)
    if entry is None or entry.shop_id != shop_id:
        raise HTTPException(status_code=404, detail="Entry not found")
    await db.delete(entry)
    await db.flush()


@router.get("/payments/shops/{shop_id}/report-settings", response_model=ReportSettings)
async def get_settings(
    shop_id: str,
    db: AsyncSession = Depends(get_db, scope="function"),
    current_user: dict = Depends(get_current_user),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
):
    await _require_shop_access(shop_id, current_user, lookup_owner)
    return await report_service.preference(db, shop_id)


@router.put("/payments/shops/{shop_id}/report-settings", response_model=ReportSettings)
async def set_settings(
    shop_id: str,
    body: ReportSettings,
    db: AsyncSession = Depends(get_db, scope="function"),
    current_user: dict = Depends(get_current_user),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
):
    """Turning WhatsApp on is the owner's consent to get reports there; the moment is kept as proof of it."""
    await _require_shop_access(shop_id, current_user, lookup_owner)
    row = await report_service.preference(db, shop_id)
    was_whatsapp = bool(row.whatsapp)
    for field, value in body.model_dump().items():
        setattr(row, field, value)
    if body.whatsapp and not was_whatsapp:
        row.whatsapp_consent_at = datetime.now(timezone.utc)
    row.updated_by = current_user["sub"]
    db.add(row)
    await db.flush()
    return row
