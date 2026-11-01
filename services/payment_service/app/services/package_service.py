"""Prepaid packages: visits of one service a shop sells together, paid for upfront.

A customer buys a package online (a PACKAGE payment, completed like any other) and books each visit
with it: booking_service redeems one visit for the booking, which then costs nothing more. The shop
earns each visit's share of the price, less commission, when that booking is completed (see
earnings_service.settle_booking); a cancelled booking gives its visit back. Once a package expires its
unused visits can no longer be booked; an admin can refund them.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import structlog
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import PackagePurchase, PackageRedemption, Payment, ServicePackage

log = structlog.get_logger()

PENDING, ACTIVE, REFUNDED = "PENDING", "ACTIVE", "REFUNDED"
USED, RETURNED = "USED", "RETURNED"


class PackageRefused(ValueError):
    """A package that cannot be used or bought as asked (with the status to answer)."""

    def __init__(self, message: str, status: int = 409):
        super().__init__(message)
        self.status = status


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _utc(at: Optional[datetime]) -> Optional[datetime]:
    return at if at is None or at.tzinfo else at.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------- what shops sell


async def create_package(
    db: AsyncSession, shop_id: str, service_id: str, name: str, visits: int, price_cents: int, valid_days: int
) -> ServicePackage:
    package = ServicePackage(
        id=str(uuid.uuid4()),
        shop_id=shop_id,
        service_id=service_id,
        name=name.strip(),
        visits=visits,
        price_cents=price_cents,
        valid_days=valid_days,
        is_active=True,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(package)
    await db.flush()
    return package


async def list_packages(
    db: AsyncSession, shop_id: Optional[str] = None, service_id: Optional[str] = None, active_only: bool = True
) -> List[ServicePackage]:
    query = select(ServicePackage).order_by(ServicePackage.created_at.desc(), ServicePackage.id)
    if shop_id:
        query = query.where(ServicePackage.shop_id == shop_id)
    if service_id:
        query = query.where(ServicePackage.service_id == service_id)
    if active_only:
        query = query.where(ServicePackage.is_active.is_(True))
    return list((await db.execute(query)).scalars().all())


# ---------------------------------------------------------------- buying


async def start_purchase(db: AsyncSession, package: ServicePackage, customer_id: str) -> PackagePurchase:
    """A purchase waiting for its payment; the package's terms are copied, so later edits never change it."""
    if not package.is_active:
        raise PackageRefused("This package is no longer offered")
    purchase = PackagePurchase(
        id=str(uuid.uuid4()),
        package_id=package.id,
        customer_id=customer_id,
        shop_id=package.shop_id,
        service_id=package.service_id,
        name=package.name,
        visits_total=package.visits,
        visits_left=package.visits,
        price_cents=package.price_cents,
        valid_days=package.valid_days,
        status=PENDING,
        created_at=_now(),
    )
    db.add(purchase)
    await db.flush()
    return purchase


async def payment_completed(db: AsyncSession, payment: Payment) -> Optional[PackagePurchase]:
    """The package's payment went through: it is ACTIVE from now, for its number of days."""
    purchase = await db.get(PackagePurchase, payment.booking_id)
    if purchase is None or purchase.status != PENDING:
        return purchase
    now = _now()
    purchase.status = ACTIVE
    purchase.payment_id = payment.id
    purchase.purchased_at = now
    purchase.expires_at = now + timedelta(days=purchase.valid_days)
    await db.flush()
    log.info("package_bought", purchase_id=purchase.id, customer_id=purchase.customer_id, shop_id=purchase.shop_id)
    return purchase


async def customer_packages(db: AsyncSession, customer_id: str) -> List[PackagePurchase]:
    """The customer's paid packages, newest first."""
    result = await db.execute(
        select(PackagePurchase)
        .where(PackagePurchase.customer_id == customer_id, PackagePurchase.status != PENDING)
        .order_by(PackagePurchase.purchased_at.desc(), PackagePurchase.id)
    )
    return list(result.scalars().all())


def usable(purchase: PackagePurchase, now: Optional[datetime] = None) -> bool:
    return (
        purchase.status == ACTIVE
        and purchase.visits_left > 0
        and purchase.expires_at is not None
        and _utc(purchase.expires_at) > (now or _now())
    )


# ---------------------------------------------------------------- using it for bookings


def _visit_value(purchase: PackagePurchase) -> int:
    """This visit's share of the price: equal shares, the last one taking what rounding left over."""
    share = purchase.price_cents // purchase.visits_total
    return purchase.price_cents - share * (purchase.visits_total - 1) if purchase.visits_left == 1 else share


async def redemption_for(db: AsyncSession, booking_id: str) -> Optional[PackageRedemption]:
    result = await db.execute(select(PackageRedemption).where(PackageRedemption.booking_id == booking_id))
    return result.scalar_one_or_none()


async def redeem(
    db: AsyncSession, customer_id: str, purchase_id: str, service_id: str, booking_id: str
) -> PackageRedemption:
    """Uses one visit of the customer's package for [booking_id]; asking again for it returns that visit."""
    earlier = await redemption_for(db, booking_id)
    if earlier is not None and earlier.status == USED:
        return earlier
    purchase = (
        await db.execute(select(PackagePurchase).where(PackagePurchase.id == purchase_id).with_for_update())
    ).scalar_one_or_none()
    if purchase is None or purchase.customer_id != customer_id:
        raise PackageRefused("Package not found", 404)
    if purchase.service_id != service_id:
        raise PackageRefused("This package is for another service", 422)
    if purchase.status != ACTIVE:
        raise PackageRefused("This package can no longer be used")
    if _utc(purchase.expires_at) <= _now():
        raise PackageRefused("This package has expired")
    if purchase.visits_left <= 0:
        raise PackageRefused("All the visits in this package have been used")
    value = _visit_value(purchase)
    purchase.visits_left -= 1
    redemption = PackageRedemption(
        id=str(uuid.uuid4()),
        purchase_id=purchase.id,
        booking_id=booking_id,
        visit_value_cents=value,
        status=USED,
        created_at=_now(),
    )
    try:
        async with db.begin_nested():
            db.add(redemption)
            await db.flush()
    except IntegrityError:  # the same booking redeemed at the same moment
        purchase.visits_left += 1
        await db.flush()
        again = await redemption_for(db, booking_id)
        if again is None:
            raise
        return again
    return redemption


async def return_visit(db: AsyncSession, booking_id: str) -> bool:
    """A booking made with a package was cancelled (or never made): its visit can be booked again."""
    redemption = await redemption_for(db, booking_id)
    if redemption is None or redemption.status != USED:
        return False
    purchase = await db.get(PackagePurchase, redemption.purchase_id)
    redemption.status = RETURNED
    if purchase is not None and purchase.status == ACTIVE:
        purchase.visits_left += 1
    await db.flush()
    return True


async def used_value_cents(db: AsyncSession, purchase_id: str) -> int:
    result = await db.execute(
        select(func.coalesce(func.sum(PackageRedemption.visit_value_cents), 0)).where(
            PackageRedemption.purchase_id == purchase_id, PackageRedemption.status == USED
        )
    )
    return int(result.scalar() or 0)


async def mark_refunded(db: AsyncSession, purchase: PackagePurchase) -> None:
    purchase.status = REFUNDED
    purchase.visits_left = 0
    await db.flush()
