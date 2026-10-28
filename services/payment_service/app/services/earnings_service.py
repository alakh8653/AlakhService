"""What shops earn from completed bookings, the platform's commission on it, and payouts to shops.

A booking's SALE earning is recorded once, when booking_service says the booking is COMPLETED:
- paid online, the escrow is released: the shop is owed the net (gross - commission - GST on commission);
- paid at the shop (cash, or never paid through us), the shop already has the money and owes the
  platform commission + GST, recorded as a negative amount netted against its next payout.

Statuses: HELD (under dispute), READY (owed, waiting for a payout), PAID (in a payout marked paid),
REFUNDED (refunded in full, nothing owed either way).
"""

import json
import uuid
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Sequence, Tuple

import structlog
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core import money
from app.core.escrow import escrow_service
from app.core.ledger import ledger
from app.models.payment import (
    BOOKING,
    TIP,
    Account,
    CommissionRate,
    Escrow,
    Payment,
    Payout,
    Refund,
    ShopEarning,
)
from app.services import loyalty_service

log = structlog.get_logger()

DEFAULT_RATE_KEY = "*"
SALE, ADJUSTMENT = "SALE", "ADJUSTMENT"
TIP_KIND, TIP_ADJUSTMENT = "TIP", "TIP_ADJUSTMENT"
ONLINE, CASH = "ONLINE", "CASH"
HELD, READY, PAID, REFUNDED = "HELD", "READY", "PAID", "REFUNDED"
GST_ACCOUNT = "gst_payable"
PAYOUT_ACCOUNT = "payouts_clearing"
# A payment whose money the booking kept (a refund may have given some of it back).
SETTLED_PAYMENT_STATUSES = ("COMPLETED", "PARTIALLY_REFUNDED", "REFUNDED")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def shop_account_owner(shop_id: str) -> str:
    return f"shop:{shop_id}"


# ---------------------------------------------------------------- commission rates


async def default_commission_percent(db: AsyncSession) -> Decimal:
    row = await db.get(CommissionRate, DEFAULT_RATE_KEY)
    return Decimal(row.commission_percent) if row else Decimal(settings.PLATFORM_COMMISSION_PERCENT)


async def rates_for(db: AsyncSession, shop_id: str) -> Tuple[Decimal, Decimal]:
    """(commission %, GST % on commission) for a shop: its own rate, else the platform default."""
    row = await db.get(CommissionRate, shop_id) if shop_id != DEFAULT_RATE_KEY else None
    commission = Decimal(row.commission_percent) if row else await default_commission_percent(db)
    return commission, Decimal(settings.GST_ON_COMMISSION_PERCENT)


async def list_overrides(db: AsyncSession) -> List[CommissionRate]:
    result = await db.execute(
        select(CommissionRate).where(CommissionRate.shop_id != DEFAULT_RATE_KEY).order_by(CommissionRate.shop_id)
    )
    return list(result.scalars().all())


async def set_rate(db: AsyncSession, shop_id: str, percent: Optional[Decimal], by: str) -> Optional[CommissionRate]:
    """Sets (or with None removes) the commission for a shop, or with "*" the platform default.

    Only bookings completed afterwards use the new rate; earnings already recorded keep theirs.
    """
    row = await db.get(CommissionRate, shop_id)
    if percent is None:
        if row:
            await db.delete(row)
            await db.flush()
        return None
    if row is None:
        row = CommissionRate(shop_id=shop_id, commission_percent=percent, updated_by=by, updated_at=_now())
        db.add(row)
    else:
        row.commission_percent = percent
        row.updated_by = by
        row.updated_at = _now()
    await db.flush()
    return row


# ---------------------------------------------------------------- recording earnings


async def _refunded_cents(db: AsyncSession, payment_id: str) -> int:
    result = await db.execute(
        select(func.coalesce(func.sum(Refund.amount_cents), 0)).where(
            Refund.payment_id == payment_id, Refund.status != "FAILED"
        )
    )
    return int(result.scalar() or 0)


async def settled_payment(db: AsyncSession, booking_id: str) -> Optional[Payment]:
    """The payment the booking kept (never a duplicate), if it was paid."""
    result = await db.execute(
        select(Payment)
        .where(
            Payment.booking_id == booking_id,
            Payment.purpose == BOOKING,
            Payment.status.in_(SETTLED_PAYMENT_STATUSES),
        )
        .order_by(Payment.created_at)
    )
    payments = list(result.scalars().all())
    # A duplicate refunded in full is REFUNDED too; the booking's own payment is preferred.
    for status in SETTLED_PAYMENT_STATUSES:
        for p in payments:
            if p.status == status:
                return p
    return None


async def sale_for(db: AsyncSession, booking_id: str, kind: str = SALE) -> Optional[ShopEarning]:
    result = await db.execute(select(ShopEarning).where(ShopEarning.booking_id == booking_id, ShopEarning.kind == kind))
    return result.scalar_one_or_none()


def _apply_split(
    earning: ShopEarning, gross: int, commission_pct: Decimal, gst_pct: Decimal, platform_discount: int = 0
) -> None:
    """[gross] is what the customer paid (and kept paid); the platform adds [platform_discount] for their
    points, so the shop earns on the full price. Nothing is added once the booking is refunded in full."""
    discount = platform_discount if gross > 0 else 0
    s = money.split(gross + discount, commission_pct, gst_pct)
    earning.gross_cents = s.gross_cents
    earning.commission_percent = commission_pct
    earning.gst_percent = gst_pct
    earning.commission_cents = s.commission_cents
    earning.gst_cents = s.gst_cents
    earning.net_cents = s.net_cents
    earning.platform_discount_cents = discount
    earning.payout_cents = money.payout_cents(s, earning.collection, discount)
    earning.updated_at = _now()


async def _gross_and_collection(
    db: AsyncSession, booking_id: str, total_amount: Optional[int]
) -> Tuple[Optional[Payment], str, int]:
    payment = await settled_payment(db, booking_id)
    if payment is not None:
        gross = payment.amount_cents - await _refunded_cents(db, payment.id)
        return payment, (CASH if payment.gateway == "cash" else ONLINE), gross
    # Never paid through the platform: paid at the shop.
    return None, CASH, int(total_amount or 0)


async def settle_booking(
    db: AsyncSession,
    booking_id: str,
    shop_id: Optional[str],
    total_amount: Optional[int],
    completed_at: Optional[datetime] = None,
    hold: bool = False,
) -> Tuple[ShopEarning, bool]:
    """Records what a completed booking earned its shop; returns (earning, created).

    Idempotent: a booking is settled once, so a repeated call (booking_service retrying) returns the
    earning already recorded.
    """
    existing = await sale_for(db, booking_id)
    if existing is not None:
        return existing, False
    payment, collection, gross = await _gross_and_collection(db, booking_id, total_amount)
    shop_id = shop_id or (payment.shop_id if payment else None)
    if not shop_id:
        raise ValueError("The booking has no shop to settle with")
    commission_pct, gst_pct = await rates_for(db, shop_id)
    points_paid = await loyalty_service.redeemed_cents(db, booking_id)
    earning = ShopEarning(
        id=str(uuid.uuid4()),
        booking_id=booking_id,
        kind=SALE,
        payment_id=payment.id if payment else None,
        shop_id=shop_id,
        collection=collection,
        currency=payment.currency if payment else "INR",
        status=HELD if hold else READY,
        completed_at=completed_at or _now(),
        created_at=_now(),
    )
    _apply_split(earning, gross, commission_pct, gst_pct, points_paid)
    if gross <= 0:
        earning.status = REFUNDED
    try:
        async with db.begin_nested():
            db.add(earning)
            await db.flush()
    except IntegrityError:  # settled at the same moment by another request
        again = await sale_for(db, booking_id)
        if again is None:
            raise
        return again, False
    if collection == ONLINE and payment is not None:
        await _release_escrow(db, payment, earning)
    log.info(
        "booking_settled",
        booking_id=booking_id,
        shop_id=shop_id,
        collection=collection,
        gross_cents=earning.gross_cents,
        commission_cents=earning.commission_cents,
        gst_cents=earning.gst_cents,
        payout_cents=earning.payout_cents,
    )
    return earning, True


async def _account(db: AsyncSession, owner_id: str, owner_type: str, currency: str) -> Account:
    from app.services.payment_service import payment_service  # avoid an import cycle

    return await payment_service.get_or_create_account(db, owner_id, owner_type, currency)


async def _release_escrow(db: AsyncSession, payment: Payment, earning: ShopEarning) -> None:
    """Moves the shop's net and the GST out of the platform's escrow in the ledger (best effort)."""
    try:
        async with db.begin_nested():
            escrow = (await db.execute(select(Escrow).where(Escrow.payment_id == payment.id))).scalar_one_or_none()
            if escrow is None or escrow.status != "HELD":
                return
            shop = await _account(db, shop_account_owner(earning.shop_id), "shop", payment.currency)
            gst = await _account(db, GST_ACCOUNT, "platform", payment.currency)
            await escrow_service.release_funds(
                db,
                payment.id,
                shop.id,
                amount_cents=max(earning.net_cents, 0),
                gst_account_id=gst.id,
                gst_cents=earning.gst_cents,
            )
    except Exception as e:  # the earning stands; finance reconciles the ledger
        log.warning("escrow_release_failed", payment_id=payment.id, error=str(e))


async def payment_completed(db: AsyncSession, payment: Payment) -> None:
    """A payment completed for a booking already settled as paid at the shop (the customer paid online
    afterwards): the earning becomes an online one, as long as it has not been paid out."""
    sale = await sale_for(db, payment.booking_id)
    if sale is None or sale.payment_id == payment.id and sale.collection == ONLINE:
        return
    if sale.payout_id is not None or sale.status == PAID:
        log.warning("late_payment_after_payout", booking_id=payment.booking_id, payment_id=payment.id)
        return
    sale.payment_id = payment.id
    sale.collection = CASH if payment.gateway == "cash" else ONLINE
    _apply_split(
        sale,
        payment.amount_cents,
        Decimal(sale.commission_percent),
        Decimal(sale.gst_percent),
        await loyalty_service.redeemed_cents(db, payment.booking_id),
    )
    await db.flush()
    if sale.collection == ONLINE:
        await _release_escrow(db, payment, sale)


def tip_provider(payment: Payment) -> Optional[str]:
    """The provider a tip is for, as recorded when the customer started it."""
    try:
        return (json.loads(payment.metadata_json) if payment.metadata_json else {}).get("provider_id")
    except ValueError:
        return None


async def tip_completed(db: AsyncSession, payment: Payment) -> ShopEarning:
    """A tip paid online: all of it is owed to the shop for the provider (no commission, no GST), in the
    next payout. Recorded once per booking, like the booking's own sale."""
    existing = await sale_for(db, payment.booking_id, TIP_KIND)
    if existing is not None:
        return existing
    earning = ShopEarning(
        id=str(uuid.uuid4()),
        booking_id=payment.booking_id,
        kind=TIP_KIND,
        payment_id=payment.id,
        shop_id=payment.shop_id,
        provider_id=tip_provider(payment),
        collection=ONLINE,
        currency=payment.currency,
        status=READY,
        completed_at=_now(),
        created_at=_now(),
    )
    _apply_split(earning, payment.amount_cents, Decimal(0), Decimal(0))
    db.add(earning)
    await db.flush()
    await _release_escrow(db, payment, earning)
    log.info("tip_recorded", booking_id=payment.booking_id, shop_id=payment.shop_id, amount_cents=payment.amount_cents)
    return earning


async def _after_tip_refund(db: AsyncSession, payment: Payment) -> None:
    """A tip refunded: what is owed shrinks, or a tip already paid out is taken back from the next payout."""
    tip = await sale_for(db, payment.booking_id, TIP_KIND)
    if tip is None or tip.payment_id != payment.id:
        return
    left = payment.amount_cents - await _refunded_cents(db, payment.id)
    if tip.status != PAID and tip.payout_id is None:
        _apply_split(tip, left, Decimal(0), Decimal(0))
        tip.status = REFUNDED if left <= 0 else READY
        await db.flush()
        return
    adjustment = await sale_for(db, payment.booking_id, TIP_ADJUSTMENT)
    if adjustment is not None and (adjustment.status == PAID or adjustment.payout_id is not None):
        log.error("tip_refund_after_adjustment_paid_out", booking_id=payment.booking_id)
        return
    if adjustment is None:
        adjustment = ShopEarning(
            id=str(uuid.uuid4()),
            booking_id=payment.booking_id,
            kind=TIP_ADJUSTMENT,
            payment_id=payment.id,
            shop_id=tip.shop_id,
            provider_id=tip.provider_id,
            collection=ONLINE,
            currency=tip.currency,
            status=READY,
            completed_at=_now(),
            created_at=_now(),
        )
        db.add(adjustment)
    _apply_split(adjustment, left - tip.gross_cents, Decimal(0), Decimal(0))
    await db.flush()


async def after_refund(db: AsyncSession, payment: Payment) -> None:
    """Brings the booking's earning in line with what is left of its payment after a refund.

    Not paid out yet: the earning itself shrinks (REFUNDED when nothing is left). Already paid out: an
    ADJUSTMENT takes the difference off the shop's next payout. A tip's refund changes only the tip.
    """
    if payment.purpose == TIP:
        return await _after_tip_refund(db, payment)
    sale = await sale_for(db, payment.booking_id)
    if sale is None or sale.payment_id not in (None, payment.id):
        return
    gross = payment.amount_cents - await _refunded_cents(db, payment.id)
    pct, gst_pct = Decimal(sale.commission_percent), Decimal(sale.gst_percent)
    points_paid = await loyalty_service.redeemed_cents(db, payment.booking_id)
    if gross <= 0:
        await loyalty_service.booking_refunded_in_full(db, payment.booking_id)
    discount = points_paid if gross > 0 else 0
    if sale.status != PAID and sale.payout_id is None:
        _apply_split(sale, gross, pct, gst_pct, points_paid)
        if gross <= 0:
            sale.status = REFUNDED
        elif sale.status == REFUNDED:  # a refund that failed after all
            sale.status = READY
        await db.flush()
        return
    owed = money.payout_cents(money.split(gross + discount, pct, gst_pct), sale.collection, discount)
    adjustment = await sale_for(db, payment.booking_id, ADJUSTMENT)
    already = sale.payout_cents + (adjustment.payout_cents if adjustment else 0)
    if owed == already:
        return
    if adjustment is not None and (adjustment.status == PAID or adjustment.payout_id is not None):
        log.error("refund_after_adjustment_paid_out", booking_id=payment.booking_id, difference=owed - already)
        return
    new = money.split(gross + discount, pct, gst_pct)
    old = money.split(sale.gross_cents, pct, gst_pct)
    if adjustment is None:
        adjustment = ShopEarning(
            id=str(uuid.uuid4()),
            booking_id=payment.booking_id,
            kind=ADJUSTMENT,
            payment_id=payment.id,
            shop_id=sale.shop_id,
            collection=sale.collection,
            currency=sale.currency,
            commission_percent=pct,
            gst_percent=gst_pct,
            status=READY,
            completed_at=_now(),
            created_at=_now(),
        )
        db.add(adjustment)
    adjustment.gross_cents = new.gross_cents - old.gross_cents
    adjustment.commission_cents = new.commission_cents - old.commission_cents
    adjustment.gst_cents = new.gst_cents - old.gst_cents
    adjustment.net_cents = new.net_cents - old.net_cents
    adjustment.payout_cents = owed - sale.payout_cents
    adjustment.updated_at = _now()
    await db.flush()


async def hold(db: AsyncSession, booking_id: str) -> Optional[ShopEarning]:
    """Keeps a disputed booking's earning out of payouts until the dispute is resolved."""
    sale = await sale_for(db, booking_id)
    if sale is not None and sale.status == READY and sale.payout_id is None:
        sale.status = HELD
        sale.updated_at = _now()
        await db.flush()
    return sale


async def release(
    db: AsyncSession, booking_id: str, shop_id: Optional[str] = None, total_amount: Optional[int] = None
) -> Optional[ShopEarning]:
    """A dispute resolved in the shop's favour: its earning is owed again (recorded now if it never was)."""
    sale = await sale_for(db, booking_id)
    if sale is None:
        payment = await settled_payment(db, booking_id)
        if payment is None and not (shop_id and total_amount):
            return None
        sale, _ = await settle_booking(db, booking_id, shop_id, total_amount)
        return sale
    if sale.status == HELD:
        sale.status = READY
        sale.updated_at = _now()
        await db.flush()
    return sale


# ---------------------------------------------------------------- reports


def _day_start(d: date) -> datetime:
    return datetime.combine(d, time.min, tzinfo=timezone.utc)


async def earnings_report(db: AsyncSession, shop_id: str, date_from: date, date_to: date) -> dict:
    """The shop's earnings for bookings completed in [date_from, date_to], with totals in rupees.

    pending_payout is what is still owed for them (HELD or READY, negative when cash commission is
    owed); paid_out what has been paid; outstanding is everything owed right now, whatever the dates.
    """
    rows = (
        (
            await db.execute(
                select(ShopEarning)
                .where(
                    ShopEarning.shop_id == shop_id,
                    ShopEarning.completed_at >= _day_start(date_from),
                    ShopEarning.completed_at < _day_start(date_to + timedelta(days=1)),
                )
                .order_by(ShopEarning.completed_at.desc(), ShopEarning.id)
            )
        )
        .scalars()
        .all()
    )
    outstanding = (
        await db.execute(
            select(func.coalesce(func.sum(ShopEarning.payout_cents), 0)).where(
                ShopEarning.shop_id == shop_id, ShopEarning.status.in_((HELD, READY))
            )
        )
    ).scalar()
    r = money.rupees
    tips = [e for e in rows if e.kind in (TIP_KIND, TIP_ADJUSTMENT)]
    by_provider: Dict[Optional[str], int] = defaultdict(int)
    for e in tips:
        by_provider[e.provider_id] += e.gross_cents
    return {
        "shop_id": shop_id,
        "currency": "INR",
        "from": date_from,
        "to": date_to,
        "gross": r(sum(e.gross_cents for e in rows)),
        "commission": r(sum(e.commission_cents for e in rows)),
        "gst_on_commission": r(sum(e.gst_cents for e in rows)),
        "net": r(sum(e.net_cents for e in rows)),
        "pending_payout": r(sum(e.payout_cents for e in rows if e.status in (HELD, READY))),
        "paid_out": r(sum(e.payout_cents for e in rows if e.status == PAID)),
        "outstanding": r(int(outstanding or 0)),
        # Tips are in the totals above too (no commission); the shop passes each on to its provider.
        "tips": r(sum(e.gross_cents for e in tips)),
        "tips_by_provider": [
            {"provider_id": p, "amount": r(cents)}
            for p, cents in sorted(by_provider.items(), key=lambda kv: -kv[1])
            if cents
        ],
        "items": [
            {
                "booking_id": e.booking_id,
                "payment_id": e.payment_id,
                "kind": e.kind,
                "collection": e.collection,
                "completed_at": e.completed_at,
                "gross": r(e.gross_cents),
                "commission": r(e.commission_cents),
                "gst_on_commission": r(e.gst_cents),
                "net": r(e.net_cents),
                "payout_amount": r(e.payout_cents),
                "commission_percent": float(e.commission_percent),
                "payout_status": e.status,
                "provider_id": e.provider_id,
                # Of gross, what the platform paid for the customer's points.
                "points_paid_by_platform": r(e.platform_discount_cents or 0),
            }
            for e in rows
        ],
    }


# ---------------------------------------------------------------- payouts


async def create_payout_batch(
    db: AsyncSession, period_to: date, created_by: str, shop_ids: Optional[Sequence[str]] = None
) -> Tuple[str, List[Payout]]:
    """One PENDING payout per shop for everything READY that was completed by [period_to].

    Cash commission a shop owes (negative earnings) is netted in. A shop whose total is zero or
    negative gets no payout; its earnings wait for the next batch, so what it owes is taken from
    what it earns next.
    """
    query = (
        select(ShopEarning)
        .where(
            ShopEarning.status == READY,
            ShopEarning.payout_id.is_(None),
            ShopEarning.completed_at < _day_start(period_to + timedelta(days=1)),
        )
        .order_by(ShopEarning.completed_at)
        .with_for_update()
    )
    if shop_ids:
        query = query.where(ShopEarning.shop_id.in_(list(shop_ids)))
    earnings = (await db.execute(query)).scalars().all()
    by_shop: Dict[str, List[ShopEarning]] = defaultdict(list)
    for e in earnings:
        by_shop[e.shop_id].append(e)
    batch_id = str(uuid.uuid4())
    payouts = []
    for shop_id, items in sorted(by_shop.items()):
        total = sum(e.payout_cents for e in items)
        if total <= 0:
            log.info("payout_skipped_not_positive", shop_id=shop_id, amount_cents=total)
            continue
        first = min(e.completed_at for e in items)
        payout = Payout(
            id=str(uuid.uuid4()),
            batch_id=batch_id,
            shop_id=shop_id,
            period_from=(first if first.tzinfo else first.replace(tzinfo=timezone.utc)).date(),
            period_to=period_to,
            amount_cents=total,
            currency=items[0].currency,
            status="PENDING",
            created_by=created_by,
            created_at=_now(),
        )
        db.add(payout)
        await db.flush()
        for e in items:
            e.payout_id = payout.id
            e.updated_at = _now()
        payouts.append(payout)
    await db.flush()
    log.info("payout_batch_created", batch_id=batch_id, payouts=len(payouts))
    return batch_id, payouts


async def list_payouts(
    db: AsyncSession,
    shop_id: Optional[str] = None,
    status: Optional[str] = None,
    batch_id: Optional[str] = None,
    page: int = 1,
    per_page: int = 50,
) -> Tuple[List[Payout], int]:
    query = select(Payout)
    if shop_id:
        query = query.where(Payout.shop_id == shop_id)
    if status:
        query = query.where(Payout.status == status)
    if batch_id:
        query = query.where(Payout.batch_id == batch_id)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = await db.execute(
        query.order_by(Payout.created_at.desc(), Payout.id).offset((page - 1) * per_page).limit(per_page)
    )
    return list(rows.scalars().all()), total


async def mark_paid(db: AsyncSession, payout_id: str, reference: str) -> Optional[Payout]:
    """Records that the money was transferred (e.g. the bank's UTR). Marking a paid payout again is a no-op."""
    payout = (await db.execute(select(Payout).where(Payout.id == payout_id).with_for_update())).scalar_one_or_none()
    if payout is None:
        return None
    if payout.status == "PAID":
        if payout.reference != reference:
            raise ValueError(f"Payout was already marked paid with reference {payout.reference}")
        return payout
    payout.status = "PAID"
    payout.paid_at = _now()
    payout.reference = reference
    items = (await db.execute(select(ShopEarning).where(ShopEarning.payout_id == payout.id))).scalars().all()
    for e in items:
        e.status = PAID
        e.updated_at = payout.paid_at
    await db.flush()
    try:
        async with db.begin_nested():
            shop = await _account(db, shop_account_owner(payout.shop_id), "shop", payout.currency)
            out = await _account(db, PAYOUT_ACCOUNT, "platform", payout.currency)
            await ledger.transfer(
                db,
                from_account_id=shop.id,
                to_account_id=out.id,
                amount_cents=payout.amount_cents,
                currency=payout.currency,
                description=f"Payout {payout.id} ({reference})",
                reference_id=payout.id,
                reference_type="payout",
            )
    except Exception as e:  # cash commission nets against online earnings outside the ledger
        log.warning("payout_ledger_failed", payout_id=payout.id, error=str(e))
    log.info("payout_marked_paid", payout_id=payout.id, amount_cents=payout.amount_cents)
    return payout
