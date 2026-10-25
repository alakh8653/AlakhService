"""Shop earnings, payouts, commission rates and invoices."""

import csv
import io
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core import money
from app.core.audit import AuditReporter, Origin, get_audit_reporter, request_origin
from app.core.peers import ShopDirectory, get_shop_directory
from app.database import get_db
from app.dependencies import OwnerLookup, get_current_user, get_shop_owner_lookup, require_admin
from app.models.payment import CommissionRate
from app.schemas.money import (
    CommissionOverride,
    CommissionSettings,
    CommissionUpdate,
    MarkPaid,
    PayoutBatchCreate,
    PayoutBatchResponse,
    PayoutList,
    PayoutResponse,
    ShopCommission,
    ShopPayout,
)
from app.services import earnings_service, invoice_service
from app.services.payment_service import payment_service

router = APIRouter()
admin_router = APIRouter(prefix="/admin/payments", dependencies=[Depends(require_admin)])

MAX_REPORT_DAYS = 366


async def _require_shop_access(shop_id: str, user: dict, lookup_owner: OwnerLookup) -> None:
    """Only the shop's owner or an admin; anyone else is told the shop does not exist."""
    if user.get("role") == "admin":
        return
    if await lookup_owner(shop_id) != user["sub"]:
        raise HTTPException(status_code=404, detail="Shop not found")


@router.get("/payments/shops/{shop_id}/earnings")
async def shop_earnings(
    shop_id: str,
    date_from: Optional[date] = Query(None, alias="from"),
    date_to: Optional[date] = Query(None, alias="to"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
):
    """The shop's earnings for bookings completed between from and to (default: the last 30 days)."""
    await _require_shop_access(shop_id, current_user, lookup_owner)
    date_to = date_to or datetime.now(timezone.utc).date()
    date_from = date_from or date_to - timedelta(days=29)
    if date_from > date_to:
        raise HTTPException(status_code=400, detail="from must not be after to")
    if (date_to - date_from).days >= MAX_REPORT_DAYS:
        raise HTTPException(status_code=400, detail=f"The range is limited to {MAX_REPORT_DAYS} days")
    return await earnings_service.earnings_report(db, shop_id, date_from, date_to)


@router.get("/payments/shops/{shop_id}/payouts", response_model=List[ShopPayout])
async def shop_payouts(
    shop_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
):
    await _require_shop_access(shop_id, current_user, lookup_owner)
    payouts, _ = await earnings_service.list_payouts(db, shop_id=shop_id, per_page=200)
    return [
        ShopPayout(
            id=p.id,
            period_from=p.period_from,
            period_to=p.period_to,
            amount=money.rupees(p.amount_cents),
            status=p.status,
            paid_at=p.paid_at,
            reference=p.reference,
        )
        for p in payouts
    ]


@router.get("/payments/{payment_id}/invoice", response_class=HTMLResponse)
async def invoice(
    payment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    shops: ShopDirectory = Depends(get_shop_directory),
):
    """The payment's invoice as printable HTML, for its customer, the shop paid, or an admin."""
    payment = await payment_service.get_payment(db, payment_id)
    if not payment or (
        current_user.get("role") != "admin" and current_user["sub"] not in (payment.payer_id, payment.payee_id)
    ):
        raise HTTPException(status_code=404, detail="Payment not found")
    if not payment.invoice_number:
        raise HTTPException(status_code=409, detail="The invoice is issued once the payment is complete")
    shop = await shops.shop(payment.shop_id) if payment.shop_id else None
    earning = await earnings_service.sale_for(db, payment.booking_id)
    commission, gst = await earnings_service.rates_for(db, payment.shop_id or earnings_service.DEFAULT_RATE_KEY)
    refunded = await payment_service.refunded_cents(db, payment.id)
    html = invoice_service.render_invoice(payment, shop, earning, commission, gst, refunded)
    return HTMLResponse(html, headers={"Cache-Control": "private, no-store"})


# ---------------------------------------------------------------- admin


def _audit(
    background: BackgroundTasks, audit: AuditReporter, user: dict, action: str, kind: str, rid: str, origin, new
):
    background.add_task(audit.record, user["sub"], action, kind, rid, origin, new_values=new)


@admin_router.get("/commission", response_model=CommissionSettings)
async def commission_settings(db: AsyncSession = Depends(get_db)):
    return CommissionSettings(
        default_commission_percent=float(await earnings_service.default_commission_percent(db)),
        configured_default_percent=float(settings.PLATFORM_COMMISSION_PERCENT),
        gst_on_commission_percent=float(settings.GST_ON_COMMISSION_PERCENT),
        overrides=[CommissionOverride.model_validate(r) for r in await earnings_service.list_overrides(db)],
    )


@admin_router.put("/commission", response_model=CommissionSettings)
async def set_default_commission(
    body: CommissionUpdate,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
    audit: AuditReporter = Depends(get_audit_reporter),
    origin: Origin = Depends(request_origin),
):
    """The default rate for shops without their own; null goes back to PLATFORM_COMMISSION_PERCENT."""
    await earnings_service.set_rate(db, earnings_service.DEFAULT_RATE_KEY, body.commission_percent, current_user["sub"])
    await db.commit()
    _audit(
        background,
        audit,
        current_user,
        "set_commission",
        "commission",
        "default",
        origin,
        {"commission_percent": None if body.commission_percent is None else float(body.commission_percent)},
    )
    return await commission_settings(db)


async def _shop_commission(db: AsyncSession, shop_id: str) -> ShopCommission:
    own = await db.get(CommissionRate, shop_id)
    commission, gst = await earnings_service.rates_for(db, shop_id)
    return ShopCommission(
        shop_id=shop_id,
        commission_percent=float(commission),
        gst_on_commission_percent=float(gst),
        source="shop" if own else "default",
    )


@admin_router.get("/commission/{shop_id}", response_model=ShopCommission)
async def shop_commission(shop_id: str, db: AsyncSession = Depends(get_db)):
    return await _shop_commission(db, shop_id)


@admin_router.put("/commission/{shop_id}", response_model=ShopCommission)
async def set_shop_commission(
    shop_id: str,
    body: CommissionUpdate,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
    audit: AuditReporter = Depends(get_audit_reporter),
    origin: Origin = Depends(request_origin),
):
    """The shop's own commission rate (null removes it). Applies to bookings completed from now on."""
    if shop_id == earnings_service.DEFAULT_RATE_KEY:
        raise HTTPException(status_code=422, detail="Use PUT /admin/payments/commission for the default")
    await earnings_service.set_rate(db, shop_id, body.commission_percent, current_user["sub"])
    await db.commit()
    pct = None if body.commission_percent is None else float(Decimal(body.commission_percent))
    _audit(background, audit, current_user, "set_commission", "shop", shop_id, origin, {"commission_percent": pct})
    return await _shop_commission(db, shop_id)


@admin_router.get("/payouts", response_model=PayoutList)
async def list_payouts(
    status: Optional[Literal["PENDING", "PAID"]] = None,
    shop_id: Optional[str] = None,
    batch_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    payouts, total = await earnings_service.list_payouts(db, shop_id, status, batch_id, page, per_page)
    return PayoutList(data=payouts, total=total, page=page, per_page=per_page)


@admin_router.post("/payouts/batches", response_model=PayoutBatchResponse, status_code=201)
async def create_payout_batch(
    body: PayoutBatchCreate,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
    audit: AuditReporter = Depends(get_audit_reporter),
    origin: Origin = Depends(request_origin),
):
    """A PENDING payout for every shop owed money for bookings completed up to period_to."""
    period_to = body.period_to or datetime.now(timezone.utc).date() - timedelta(days=1)
    batch_id, payouts = await earnings_service.create_payout_batch(db, period_to, current_user["sub"], body.shop_ids)
    await db.commit()
    total = sum(p.amount_cents for p in payouts)
    _audit(
        background,
        audit,
        current_user,
        "create_payout_batch",
        "payout_batch",
        batch_id,
        origin,
        {"period_to": period_to.isoformat(), "payouts": len(payouts), "amount_cents": total},
    )
    return PayoutBatchResponse(batch_id=batch_id, payouts=payouts, total_amount_cents=total)


@admin_router.post("/payouts/{payout_id}/mark-paid", response_model=PayoutResponse)
async def mark_payout_paid(
    payout_id: str,
    body: MarkPaid,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
    audit: AuditReporter = Depends(get_audit_reporter),
    origin: Origin = Depends(request_origin),
):
    """Records the bank transfer (its UTR or reference) for a payout. Repeating it changes nothing."""
    try:
        payout = await earnings_service.mark_paid(db, payout_id, body.reference.strip())
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    if payout is None:
        raise HTTPException(status_code=404, detail="Payout not found")
    await db.commit()
    _audit(
        background,
        audit,
        current_user,
        "mark_payout_paid",
        "payout",
        payout.id,
        origin,
        {"reference": payout.reference, "amount_cents": payout.amount_cents},
    )
    return payout


CSV_COLUMNS = [
    "payout_id",
    "batch_id",
    "shop_id",
    "amount",
    "currency",
    "period_from",
    "period_to",
    "method",
    "account_name",
    "account_number",
    "ifsc",
    "upi_id",
    "status",
    "reference",
    "note",
]


def _csv_cell(value) -> str:
    """Keeps a spreadsheet from running a cell as a formula (CSV injection)."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


@admin_router.get("/payouts/export.csv")
async def export_payouts(
    batch_id: Optional[str] = None,
    status: Optional[Literal["PENDING", "PAID"]] = "PENDING",
    db: AsyncSession = Depends(get_db),
    shops: ShopDirectory = Depends(get_shop_directory),
):
    """Payouts with each shop's bank or UPI details (from shop_service), for the bank's bulk upload."""
    payouts, _ = await earnings_service.list_payouts(db, status=status, batch_id=batch_id, per_page=10_000)
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(CSV_COLUMNS)
    details_by_shop: dict = {}
    for p in payouts:
        if p.shop_id not in details_by_shop:
            details_by_shop[p.shop_id] = await shops.payout_details(p.shop_id)
        d = details_by_shop[p.shop_id] or {}
        writer.writerow(
            [
                _csv_cell(v)
                for v in (
                    p.id,
                    p.batch_id,
                    p.shop_id,
                    f"{p.amount_cents / 100:.2f}",
                    p.currency,
                    p.period_from,
                    p.period_to,
                    d.get("method"),
                    d.get("account_name"),
                    d.get("account_number"),
                    d.get("ifsc"),
                    d.get("upi_id"),
                    p.status,
                    p.reference,
                    "" if d else "Payout details missing: ask the shop to add them",
                )
            ]
        )
    name = f"payouts-{batch_id or status or 'all'}.csv"
    return Response(
        out.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store"},
    )
