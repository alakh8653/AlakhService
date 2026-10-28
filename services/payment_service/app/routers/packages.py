"""Prepaid packages: shops offer them, customers buy and use them (see app.services.package_service)."""

from datetime import datetime, timezone
from typing import List, Optional

import redis.asyncio as aioredis
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.internal import require_internal
from app.core.razorpay import GatewayError, RazorpayGateway, get_razorpay
from app.database import get_db
from app.dependencies import (
    OwnerLookup,
    ServiceLookup,
    get_current_user,
    get_redis,
    get_service_lookup,
    get_shop_owner_lookup,
    require_admin,
)
from app.models.payment import PACKAGE, PackagePurchase, ServicePackage
from app.routers.payments import _with_checkout
from app.schemas.payment import PaymentCheckoutResponse, PaymentInitiate, RefundRequest
from app.services import package_service
from app.services.payment_service import payment_service

router = APIRouter()
internal_router = APIRouter(prefix="/internal/payments/packages", dependencies=[Depends(require_internal)])
log = structlog.get_logger()


class PackageCreate(BaseModel):
    shop_id: str
    service_id: str
    name: str = Field(min_length=2, max_length=100)
    visits: int = Field(ge=2, le=50)
    price_cents: int = Field(ge=100, le=10_000_000)
    valid_days: int = Field(ge=7, le=730)


class PackageUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    price_cents: Optional[int] = Field(default=None, ge=100, le=10_000_000)
    valid_days: Optional[int] = Field(default=None, ge=7, le=730)
    is_active: Optional[bool] = None


class PackageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    shop_id: str
    service_id: str
    name: str
    visits: int
    price_cents: int
    valid_days: int
    is_active: bool


class PurchaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    package_id: str
    shop_id: str
    service_id: str
    name: str
    visits_total: int
    visits_left: int
    price_cents: int
    status: str
    purchased_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    # ACTIVE, with visits left, and not expired: it can be used for a booking now.
    usable: bool = False


class PackageCheckout(BaseModel):
    payment_method: str = Field(pattern="^(upi|card|netbanking|wallet)$")
    idempotency_key: str = Field(min_length=8, max_length=128)


class PackageCheckoutResponse(BaseModel):
    purchase_id: str
    payment: PaymentCheckoutResponse


class PackageRedeem(BaseModel):
    customer_id: str
    purchase_id: str
    service_id: str
    booking_id: str


class PackageRelease(BaseModel):
    booking_id: str


def _purchase_out(p: PackagePurchase) -> PurchaseOut:
    out = PurchaseOut.model_validate(p)
    out.usable = package_service.usable(p)
    return out


async def _own_shop(shop_id: str, user: dict, lookup_owner: OwnerLookup) -> None:
    if user.get("role") != "admin" and await lookup_owner(shop_id) != user["sub"]:
        raise HTTPException(status_code=403, detail="Only the shop's owner can manage its packages")


@router.get("/packages", response_model=List[PackageOut])
async def list_packages(
    shop_id: Optional[str] = Query(None, max_length=128),
    service_id: Optional[str] = Query(None, max_length=128),
    db: AsyncSession = Depends(get_db),
):
    """Packages on offer, for a shop or a service (public)."""
    if not shop_id and not service_id:
        raise HTTPException(status_code=422, detail="Give a shop_id or a service_id")
    return await package_service.list_packages(db, shop_id, service_id)


@router.get("/packages/shop/{shop_id}", response_model=List[PackageOut])
async def shop_packages(
    shop_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
):
    """All of a shop's packages, those no longer offered included, for its owner."""
    await _own_shop(shop_id, current_user, lookup_owner)
    return await package_service.list_packages(db, shop_id, active_only=False)


@router.post("/packages", response_model=PackageOut, status_code=201)
async def create_package(
    body: PackageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
    lookup_service: ServiceLookup = Depends(get_service_lookup),
):
    await _own_shop(body.shop_id, current_user, lookup_owner)
    service = await lookup_service(body.service_id)
    if service is None or service.get("shop_id") != body.shop_id:
        raise HTTPException(status_code=422, detail="Choose one of your shop's services")
    package = await package_service.create_package(
        db, body.shop_id, body.service_id, body.name, body.visits, body.price_cents, body.valid_days
    )
    log.info("package_created", package_id=package.id, shop_id=body.shop_id)
    return package


@router.patch("/packages/{package_id}", response_model=PackageOut)
async def update_package(
    package_id: str,
    body: PackageUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
):
    """Changes what new buyers get; packages already bought keep their terms."""
    package = await db.get(ServicePackage, package_id)
    if package is None:
        raise HTTPException(status_code=404, detail="Package not found")
    await _own_shop(package.shop_id, current_user, lookup_owner)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(package, field, value.strip() if isinstance(value, str) else value)
    package.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return package


@router.post("/packages/{package_id}/buy", response_model=PackageCheckoutResponse, status_code=201)
async def buy_package(
    package_id: str,
    checkout: PackageCheckout,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    current_user: dict = Depends(get_current_user),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
    gateway: RazorpayGateway = Depends(get_razorpay),
):
    """Buy a package, paid online; it is ACTIVE once the payment completes (``/payments/{id}/verify``)."""
    if not gateway.configured:
        raise HTTPException(status_code=503, detail="Packages can only be paid online, which is not available yet")
    customer_id = current_user["sub"]
    earlier = await payment_service.payment_by_key(db, checkout.idempotency_key)
    if earlier is not None:  # a retry: the same purchase and payment
        if earlier.payer_id != customer_id or earlier.purpose != PACKAGE:
            raise HTTPException(status_code=409, detail="Idempotency key already used")
        return PackageCheckoutResponse(purchase_id=earlier.booking_id, payment=_with_checkout(earlier, gateway))
    package = await db.get(ServicePackage, package_id)
    if package is None or not package.is_active:
        raise HTTPException(status_code=404, detail="Package not found")
    payee_id = await lookup_owner(package.shop_id)
    if not payee_id:
        raise HTTPException(status_code=409, detail="This shop cannot be paid yet")
    purchase = await package_service.start_purchase(db, package, customer_id)
    payment = await payment_service.initiate_payment(
        db,
        redis,
        PaymentInitiate(
            booking_id=purchase.id,
            payer_id=customer_id,
            payee_id=payee_id,
            shop_id=package.shop_id,
            amount_cents=package.price_cents,
            payment_method=checkout.payment_method,
            idempotency_key=checkout.idempotency_key,
            purpose=PACKAGE,
        ),
    )
    try:
        payment.provider_order_id = await gateway.create_order(
            payment.amount_cents,
            payment.currency,
            receipt=payment.id,
            notes={"payment_id": payment.id, "purchase_id": purchase.id, "purpose": PACKAGE},
        )
    except GatewayError as e:
        log.warning("razorpay_order_failed", payment_id=payment.id, error=str(e))
        raise HTTPException(status_code=502, detail="Could not start the payment. Please try again.") from e
    payment.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return PackageCheckoutResponse(purchase_id=purchase.id, payment=_with_checkout(payment, gateway))


@router.get("/packages/mine", response_model=List[PurchaseOut])
async def my_packages(db: AsyncSession = Depends(get_db), current_user: dict = Depends(get_current_user)):
    return [_purchase_out(p) for p in await package_service.customer_packages(db, current_user["sub"])]


@router.post("/admin/payments/packages/{purchase_id}/refund", response_model=PurchaseOut)
async def refund_unused_visits(
    purchase_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
    gateway: RazorpayGateway = Depends(get_razorpay),
):
    """Refunds what is left of a package (its price less the visits already used) and closes it."""
    purchase = await db.get(PackagePurchase, purchase_id)
    if purchase is None or purchase.status != package_service.ACTIVE or not purchase.payment_id:
        raise HTTPException(status_code=404, detail="No paid package to refund")
    unused = purchase.price_cents - await package_service.used_value_cents(db, purchase.id)
    if unused > 0:
        try:
            await payment_service.request_refund(
                db,
                purchase.payment_id,
                RefundRequest(amount_cents=unused, reason="Unused package visits"),
                gateway,
                idempotency_key=f"package:{purchase.id}",
            )
        except GatewayError as e:
            raise HTTPException(status_code=502, detail="Razorpay could not process the refund") from e
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    await package_service.mark_refunded(db, purchase)
    log.info("package_refunded", purchase_id=purchase.id, by=current_user["sub"], amount_cents=unused)
    return _purchase_out(purchase)


@internal_router.post("/redeem")
async def redeem_visit(body: PackageRedeem, db: AsyncSession = Depends(get_db)):
    """booking_service uses one visit of the customer's package for a booking it is making."""
    try:
        visit = await package_service.redeem(db, body.customer_id, body.purchase_id, body.service_id, body.booking_id)
    except package_service.PackageRefused as e:
        raise HTTPException(status_code=e.status, detail=str(e)) from e
    purchase = await db.get(PackagePurchase, visit.purchase_id)
    return {
        "booking_id": body.booking_id,
        "visit_value_cents": visit.visit_value_cents,
        "visits_left": purchase.visits_left,
    }


@internal_router.post("/release")
async def release_visit(body: PackageRelease, db: AsyncSession = Depends(get_db)):
    """A booking the visit was used for was never made after all: the visit can be booked again."""
    return {"booking_id": body.booking_id, "returned": await package_service.return_visit(db, body.booking_id)}
