"""Read-only finance reports over payments, refunds and escrow."""
from datetime import date, datetime, time, timedelta, timezone
from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Escrow, Payment, Refund
from app.schemas.finance import RevenuePoint, RevenueReport, Settlement

# Payments whose money was collected (later refunds are reported separately).
COLLECTED_STATUSES = ("COMPLETED", "PARTIALLY_REFUNDED", "REFUNDED")


def _day_bounds(date_from: date, date_to: date) -> Tuple[datetime, datetime]:
    start = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
    end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
    return start, end


async def list_settlements(
    db: AsyncSession, status: Optional[str] = None, page: int = 1, per_page: int = 20
) -> Tuple[List[Settlement], int]:
    query = select(Escrow, Payment.payee_id).join(Payment, Payment.id == Escrow.payment_id)
    if status:
        query = query.where(Escrow.status == status)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = await db.execute(
        query.order_by(Escrow.held_at.desc(), Escrow.id).offset((page - 1) * per_page).limit(per_page)
    )
    settlements = [
        Settlement(
            id=escrow.id,
            payment_id=escrow.payment_id,
            booking_id=escrow.booking_id,
            payee_id=payee_id,
            amount_cents=escrow.amount_cents,
            currency=escrow.currency,
            status=escrow.status,
            held_at=escrow.held_at,
            released_at=escrow.released_at,
        )
        for escrow, payee_id in rows.all()
    ]
    return settlements, total


async def revenue_report(db: AsyncSession, date_from: date, date_to: date, currency: str = "INR") -> RevenueReport:
    """Daily gross collected, refunds and net for one currency, with empty days filled in."""
    start, end = _day_bounds(date_from, date_to)

    pay_day = func.date(Payment.created_at)
    gross_rows = await db.execute(
        select(pay_day, func.sum(Payment.amount_cents), func.count())
        .where(
            Payment.status.in_(COLLECTED_STATUSES),
            Payment.currency == currency,
            Payment.created_at >= start,
            Payment.created_at < end,
        )
        .group_by(pay_day)
    )
    refund_day = func.date(Refund.created_at)
    refund_rows = await db.execute(
        select(refund_day, func.sum(Refund.amount_cents))
        .join(Payment, Payment.id == Refund.payment_id)
        .where(
            Refund.status != "FAILED",
            Payment.currency == currency,
            Refund.created_at >= start,
            Refund.created_at < end,
        )
        .group_by(refund_day)
    )

    def as_date(value) -> date:  # SQLite returns 'YYYY-MM-DD' strings, PostgreSQL returns dates
        return value if isinstance(value, date) else date.fromisoformat(str(value))

    gross = {as_date(day): (int(total), int(count)) for day, total, count in gross_rows.all()}
    refunds = {as_date(day): int(total) for day, total in refund_rows.all()}

    series = []
    day = date_from
    while day <= date_to:
        g, n = gross.get(day, (0, 0))
        r = refunds.get(day, 0)
        series.append(RevenuePoint(date=day, gross_cents=g, refunds_cents=r, net_cents=g - r, payments=n))
        day += timedelta(days=1)

    gross_total = sum(p.gross_cents for p in series)
    refunds_total = sum(p.refunds_cents for p in series)
    return RevenueReport(
        currency=currency,
        date_from=date_from,
        date_to=date_to,
        gross_cents=gross_total,
        refunds_cents=refunds_total,
        net_cents=gross_total - refunds_total,
        payments=sum(p.payments for p in series),
        series=series,
    )
