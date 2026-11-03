"""A shop's profit and loss for a day, week, month or financial year, in India time.

Earned is what completed bookings left after commission and GST on it, plus income the owner wrote down;
expenses are only what the owner wrote down. So profit is as complete as their entries, and the reports say so.
Tips are shown but not counted: they go to whoever did the job.
"""

import csv
import io
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Dict, List, Literal, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.money import IST, rupees
from app.models.payment import ShopCashEntry, ShopEarning, ShopReportPreference
from app.services.earnings_service import TIP_ADJUSTMENT, TIP_KIND

Period = Literal["daily", "weekly", "monthly", "yearly"]
PERIODS: Tuple[str, ...] = ("daily", "weekly", "monthly", "yearly")
EXPENSE, INCOME = "EXPENSE", "INCOME"
NOTE = "Profit counts only what is recorded here: add your expenses and outside income for a true figure."


def _financial_year_start(day: date) -> date:
    return date(day.year if day.month >= 4 else day.year - 1, 4, 1)


def period_range(period: str, on: date) -> Tuple[date, date]:
    """First and last day of the period containing [on]. A year is India's financial year, April to March."""
    if period == "daily":
        return on, on
    if period == "weekly":
        start = on - timedelta(days=on.weekday())
        return start, start + timedelta(days=6)
    if period == "monthly":
        start = on.replace(day=1)
        return start, (start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    start = _financial_year_start(on)
    return start, date(start.year + 1, 3, 31)


def period_label(period: str, start: date, end: date) -> str:
    if period == "daily":
        return start.strftime("%d %b %Y")
    if period == "weekly":
        return f"{start.strftime('%d %b')} to {end.strftime('%d %b %Y')}"
    if period == "monthly":
        return start.strftime("%B %Y")
    return f"FY {start.year}-{str(end.year)[2:]}"


def ist_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=IST).astimezone(timezone.utc)


def _ist_day(moment: datetime) -> date:
    # SQLite in the tests gives back naive values; both databases store UTC.
    aware = moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)
    return aware.astimezone(IST).date()


async def _earnings(db: AsyncSession, shop_id: str, start: date, end: date) -> List[ShopEarning]:
    result = await db.execute(
        select(ShopEarning).where(
            ShopEarning.shop_id == shop_id,
            ShopEarning.completed_at >= ist_start(start),
            ShopEarning.completed_at < ist_start(end + timedelta(days=1)),
        )
    )
    return list(result.scalars().all())


async def list_entries(db: AsyncSession, shop_id: str, start: date, end: date) -> List[ShopCashEntry]:
    result = await db.execute(
        select(ShopCashEntry)
        .where(ShopCashEntry.shop_id == shop_id, ShopCashEntry.on_date >= start, ShopCashEntry.on_date <= end)
        .order_by(ShopCashEntry.on_date.desc(), ShopCashEntry.created_at.desc())
    )
    return list(result.scalars().all())


def _is_tip(e: ShopEarning) -> bool:
    return e.kind in (TIP_KIND, TIP_ADJUSTMENT)


def _figures(rows: List[ShopEarning], entries: List[ShopCashEntry]) -> Dict[str, int]:
    """All in paise."""
    sales = [e for e in rows if not _is_tip(e)]
    earned = sum(e.net_cents for e in sales)
    other = sum(x.amount_cents for x in entries if x.kind == INCOME)
    spent = sum(x.amount_cents for x in entries if x.kind == EXPENSE)
    return {
        "gross": sum(e.gross_cents for e in sales),
        "commission": sum(e.commission_cents for e in sales),
        "gst": sum(e.gst_cents for e in sales),
        "earned": earned,
        "cash": sum(e.gross_cents for e in sales if e.collection == "CASH"),
        "online": sum(e.gross_cents for e in sales if e.collection == "ONLINE"),
        "tips": sum(e.gross_cents for e in rows if _is_tip(e)),
        "other_income": other,
        "expenses": spent,
        "profit": earned + other - spent,
    }


def _change_percent(now: int, before: int) -> Optional[float]:
    """Against the period before; nothing to compare with when that was zero."""
    return round((now - before) * 100 / abs(before), 1) if before else None


def _breakdown(period: str, start: date, end: date, rows, entries) -> List[dict]:
    """By day, or by month for a year. Days and months with nothing are left out."""
    key = (lambda d: d.strftime("%b %Y")) if period == "yearly" else (lambda d: d.isoformat())
    earned: Dict[str, int] = defaultdict(int)
    spent: Dict[str, int] = defaultdict(int)
    for e in rows:
        if not _is_tip(e):
            earned[key(_ist_day(e.completed_at))] += e.net_cents
    for x in entries:
        if x.kind == INCOME:
            earned[key(x.on_date)] += x.amount_cents
        else:
            spent[key(x.on_date)] += x.amount_cents
    out = []
    day = start
    seen = set()
    while day <= end:
        k = key(day)
        if k not in seen and (k in earned or k in spent):
            out.append(
                {
                    "label": k,
                    "earned": rupees(earned[k]),
                    "expenses": rupees(spent[k]),
                    "profit": rupees(earned[k] - spent[k]),
                }
            )
        seen.add(k)
        day += timedelta(days=1)
    return out


async def build(db: AsyncSession, shop_id: str, period: str, on: date) -> dict:
    start, end = period_range(period, on)
    rows = await _earnings(db, shop_id, start, end)
    entries = await list_entries(db, shop_id, start, end)
    now = _figures(rows, entries)
    before_start, before_end = period_range(period, start - timedelta(days=1))
    before = _figures(
        await _earnings(db, shop_id, before_start, before_end),
        await list_entries(db, shop_id, before_start, before_end),
    )
    by_category: Dict[str, int] = defaultdict(int)
    for x in entries:
        if x.kind == EXPENSE:
            by_category[x.category] += x.amount_cents
    breakdown = _breakdown(period, start, end, rows, entries)
    return {
        "shop_id": shop_id,
        "period": period,
        "label": period_label(period, start, end),
        "from": start,
        "to": end,
        "currency": "INR",
        # A refunded booking keeps its row with nothing earned, so it is not counted as done.
        "bookings": sum(1 for e in rows if e.kind == "SALE" and e.gross_cents > 0),
        **{k: rupees(v) for k, v in now.items()},
        "previous_profit": rupees(before["profit"]),
        "profit_change_percent": _change_percent(now["profit"], before["profit"]),
        "expenses_by_category": [
            {"category": c, "amount": rupees(v)} for c, v in sorted(by_category.items(), key=lambda kv: -kv[1])
        ],
        "breakdown": breakdown,
        "best": max(breakdown, key=lambda b: b["profit"])["label"] if breakdown else None,
        "note": NOTE,
    }


def to_csv(report: dict) -> str:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["AlakhService report", report["label"]])
    for label, key in (
        ("Bookings completed", "bookings"),
        ("Customers paid", "gross"),
        ("Paid in cash", "cash"),
        ("Paid online", "online"),
        ("Platform commission", "commission"),
        ("GST on commission", "gst"),
        ("You earned from bookings", "earned"),
        ("Other income", "other_income"),
        ("Expenses", "expenses"),
        ("Profit", "profit"),
        ("Tips (not in profit)", "tips"),
    ):
        w.writerow([label, report[key]])
    w.writerow([])
    w.writerow(["Expense type", "Amount"])
    for row in report["expenses_by_category"]:
        w.writerow([row["category"], row["amount"]])
    w.writerow([])
    w.writerow(["Date" if report["period"] != "yearly" else "Month", "Earned", "Expenses", "Profit"])
    for row in report["breakdown"]:
        w.writerow([row["label"], row["earned"], row["expenses"], row["profit"]])
    w.writerow([])
    w.writerow([report["note"]])
    return out.getvalue()


def default_preference(shop_id: str) -> ShopReportPreference:
    """By email for every period; WhatsApp only after the owner says yes, as WhatsApp requires."""
    return ShopReportPreference(
        shop_id=shop_id, daily=True, weekly=True, monthly=True, yearly=True, email=True, whatsapp=False
    )


async def preference(db: AsyncSession, shop_id: str) -> ShopReportPreference:
    return await db.get(ShopReportPreference, shop_id) or default_preference(shop_id)
