"""Money rules: commission and GST on it, the cancellation refund policy, and invoice series.

Amounts are integer paise. Percentages are Decimals, and a fraction of a paisa is rounded half up
(0.5 paise and more becomes a paisa), the way GST amounts are rounded on Indian invoices.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def percent_of(amount_cents: int, percent: Decimal) -> int:
    """[percent]% of [amount_cents], rounded half up to a whole paisa."""
    return int((Decimal(amount_cents) * Decimal(percent) / Decimal(100)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class Split:
    gross_cents: int
    commission_cents: int
    gst_cents: int

    @property
    def net_cents(self) -> int:
        """What the shop keeps."""
        return self.gross_cents - self.commission_cents - self.gst_cents

    @property
    def platform_cents(self) -> int:
        return self.commission_cents + self.gst_cents


def split(gross_cents: int, commission_percent: Decimal, gst_percent: Decimal) -> Split:
    """The platform's commission on [gross_cents] and the GST on that commission."""
    commission = percent_of(gross_cents, commission_percent)
    gst = percent_of(commission, gst_percent)
    return Split(gross_cents, commission, gst)


def payout_cents(s: Split, collection: str) -> int:
    """What the platform owes the shop for a booking: the net when the platform collected the money,
    or minus commission and GST when the shop collected it in cash."""
    return s.net_cents if collection == "ONLINE" else -s.platform_cents


@dataclass(frozen=True)
class CancelRefund:
    refund_cents: int
    fee_cents: int
    rule: str


def _utc(at: datetime) -> datetime:
    return at if at.tzinfo else at.replace(tzinfo=timezone.utc)


def cancel_refund(
    paid_cents: int,
    cancelled_by: str,
    scheduled_at: Optional[datetime],
    cancelled_at: datetime,
    free_hours: float,
    fee_percent: Decimal,
) -> CancelRefund:
    """How much of [paid_cents] goes back when a booking is cancelled.

    The shop or an admin cancelling, or a customer cancelling at least [free_hours] before the booking,
    refunds everything. A customer cancelling later loses [fee_percent] of it.
    """
    if cancelled_by != "customer":
        return CancelRefund(paid_cents, 0, f"cancelled by {cancelled_by}")
    if scheduled_at is None or _utc(scheduled_at) - _utc(cancelled_at) >= timedelta(hours=free_hours):
        return CancelRefund(paid_cents, 0, "cancelled in time")
    fee = min(paid_cents, percent_of(paid_cents, fee_percent))
    return CancelRefund(paid_cents - fee, fee, "late cancellation")


def financial_year(at: datetime) -> str:
    """The Indian financial year (April to March) of a moment, as "2026-27"."""
    day: date = _utc(at).astimezone(IST).date()
    start = day.year if day.month >= 4 else day.year - 1
    return f"{start}-{(start + 1) % 100:02d}"


def invoice_series(prefix: str, at: datetime) -> str:
    return f"{prefix}/{financial_year(at)}"


def invoice_number(series: str, n: int) -> str:
    return f"{series}/{n:06d}"


def rupees(cents: int) -> float:
    """Paise as rupees with two decimals, for JSON."""
    return round(cents / 100, 2)
