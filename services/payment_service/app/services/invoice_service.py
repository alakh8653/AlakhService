"""Invoice numbers and the printable invoice for a payment.

Numbers run per Indian financial year (ALK/2026-27/000001, ...). One is taken when a payment completes,
in the same transaction, from a counter row locked for the update: a payment that does not commit
gives its number back, so a series has no gaps and no number twice.
"""

from datetime import datetime, timezone
from decimal import Decimal
from html import escape
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core import money
from app.models.payment import InvoiceSequence, Payment, ShopEarning


async def next_invoice_number(db: AsyncSession, at: datetime) -> str:
    series = money.invoice_series(settings.INVOICE_PREFIX, at)
    insert = pg_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
    await db.execute(insert(InvoiceSequence).values(series=series, last_number=0).on_conflict_do_nothing())
    row = (
        await db.execute(
            select(InvoiceSequence)
            .where(InvoiceSequence.series == series)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    row.last_number += 1
    await db.flush()
    return money.invoice_number(series, row.last_number)


async def assign_invoice(db: AsyncSession, payment: Payment) -> None:
    if payment.invoice_number:
        return
    at = datetime.now(timezone.utc)
    payment.invoice_number = await next_invoice_number(db, at)
    payment.invoice_issued_at = at
    # Set explicitly so the column's server-side onupdate does not expire it after the flush.
    payment.updated_at = at
    await db.flush()


def _inr(cents: int) -> str:
    return f"₹{cents / 100:,.2f}"


def render_invoice(
    payment: Payment,
    shop: Optional[dict],
    earning: Optional[ShopEarning],
    commission_percent: Decimal,
    gst_percent: Decimal,
    refunded_cents: int = 0,
) -> str:
    """A printable HTML invoice: the booking's amount, the platform fee in it and GST on that fee."""
    if earning is not None and earning.kind == "SALE" and earning.gross_cents == payment.amount_cents - refunded_cents:
        commission_percent, gst_percent = Decimal(earning.commission_percent), Decimal(earning.gst_percent)
    split = money.split(payment.amount_cents - refunded_cents, commission_percent, gst_percent)
    shop = shop or {}
    shop_name = shop.get("legal_name") or shop.get("name") or "The service provider"
    shop_gstin = (shop.get("gstin") or "").strip()
    shop_address = shop.get("legal_address") or shop.get("address") or ""
    issued = payment.invoice_issued_at or payment.updated_at
    issued_text = money._utc(issued).astimezone(money.IST).strftime("%d %b %Y") if issued else ""
    e = escape
    refund_row = (
        f"<tr><td>Refunded</td><td class='amt'>-{_inr(refunded_cents)}</td></tr>"
        f"<tr><td><strong>Amount kept</strong></td><td class='amt'><strong>{_inr(split.gross_cents)}</strong></td></tr>"
        if refunded_cents
        else ""
    )
    gstin_line = f"GSTIN: {e(shop_gstin)}" if shop_gstin else "GSTIN: not registered / not provided"
    shop_note = (
        "The service amount is charged by the shop above under its GSTIN."
        if shop_gstin
        else "This is not a tax invoice for the shop's service, because the shop's GSTIN is not shown. "
        "It is a receipt of what you paid through AlakhService."
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Invoice {e(payment.invoice_number or "")}</title>
<style>
body {{ font-family: system-ui, -apple-system, "Segoe UI", sans-serif; color: #111; background: #fff;
  max-width: 760px; margin: 24px auto; padding: 0 16px; font-size: 14px; }}
h1 {{ font-size: 20px; margin: 0 0 4px; }}
.muted {{ color: #555; }}
.parties {{ display: flex; gap: 24px; flex-wrap: wrap; margin: 20px 0; }}
.parties > div {{ flex: 1 1 260px; border: 1px solid #ddd; border-radius: 8px; padding: 12px; }}
table {{ width: 100%; border-collapse: collapse; margin: 16px 0; }}
td, th {{ padding: 8px; border-bottom: 1px solid #eee; text-align: left; }}
.amt {{ text-align: right; white-space: nowrap; }}
.note {{ font-size: 12px; color: #444; border-top: 1px solid #ddd; padding-top: 12px; }}
@media print {{ .noprint {{ display: none; }} body {{ margin: 0; }} }}
</style></head>
<body>
<button class="noprint" onclick="window.print()">Print / Save as PDF</button>
<h1>Invoice</h1>
<div class="muted">No. <strong>{e(payment.invoice_number or "")}</strong> &middot; Date {e(issued_text)}</div>
<div class="muted">Booking {e(payment.booking_id)} &middot; Payment {e(payment.id)} &middot; {e(payment.payment_method)}</div>
<div class="parties">
  <div><strong>Platform</strong><br>{e(settings.PLATFORM_LEGAL_NAME)}<br>{e(settings.PLATFORM_ADDRESS)}<br>
  GSTIN: {e(settings.PLATFORM_GSTIN)}</div>
  <div><strong>Service provider</strong><br>{e(shop_name)}<br>{e(shop_address)}<br>{gstin_line}</div>
</div>
<table>
<tr><th>Description</th><th class="amt">Amount</th></tr>
<tr><td>Service amount paid</td><td class="amt">{_inr(payment.amount_cents)}</td></tr>
{refund_row}
<tr><td class="muted">of which platform fee ({commission_percent.normalize():f}%), charged to the shop</td>
<td class="amt muted">{_inr(split.commission_cents)}</td></tr>
<tr><td class="muted">GST {gst_percent.normalize():f}% on the platform fee</td>
<td class="amt muted">{_inr(split.gst_cents)}</td></tr>
</table>
<div class="note">
<p>{e(shop_note)}</p>
<p>The platform fee and the GST on it are charged by {e(settings.PLATFORM_LEGAL_NAME)} to the shop and are
already included in the amount above; you were not charged anything extra. GST is shown as a single
{gst_percent.normalize():f}% line: it is CGST + SGST for a shop in the platform's state and IGST otherwise.</p>
<p>All amounts in Indian Rupees.</p>
</div>
</body></html>
"""
