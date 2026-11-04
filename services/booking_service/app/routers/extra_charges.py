"""Extra charges: what a job really costs once the provider has seen it, and only if the customer agrees.

The shop or its provider asks; the customer approves or declines in the app. Until they approve, the price does
not move, and declining leaves the booking at its price. Refused once the booking is paid or covered by a package:
the one payment a booking has cannot grow.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import ADMIN, PROVIDER, SHOP_OWNER, OwnerLookup
from app.core.fsm import BookingStatus
from app.core.live_queue import WALK_IN_PREFIX
from app.core.names import NameLookup, get_name_lookup
from app.core.notifier import Notifier, get_notifier, notify_booking, snapshot
from app.core.payments import OpenPaymentCloser, get_open_payment_closer
from app.core.privacy import masked, present
from app.database import get_db
from app.dependencies import get_current_user, get_shop_owner_lookup
from app.models.booking import Booking, BookingExtraCharge
from app.routers.bookings import _visible_booking, manager
from app.schemas.booking import BookingResponse

router = APIRouter()

PENDING, APPROVED, DECLINED, WITHDRAWN, EXPIRED = "PENDING", "APPROVED", "DECLINED", "WITHDRAWN", "EXPIRED"
# From when a provider can have seen the job until it is finished.
OPEN_STATUSES = {
    BookingStatus.CONFIRMED.value,
    BookingStatus.ASSIGNED.value,
    BookingStatus.PROVIDER_EN_ROUTE.value,
    BookingStatus.PICKED_UP.value,
    BookingStatus.IN_PROGRESS.value,
    BookingStatus.OUT_FOR_DELIVERY.value,
}
# ₹5 lakh: a typing slip of a few zeros should not reach a customer as a real request.
MAX_EXTRA_CENTS = 50_000_000


class ExtraChargeCreate(BaseModel):
    amount_cents: int = Field(gt=0, le=MAX_EXTRA_CENTS)
    reason: str = Field(min_length=3, max_length=200)

    @field_validator("reason")
    @classmethod
    def trimmed(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Say what the extra charge is for")
        return v


class ExtraChargeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    booking_id: str
    amount_cents: int
    reason: str
    status: str
    created_at: datetime
    decided_at: Optional[datetime] = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _rupees(cents: int) -> str:
    return f"₹{cents / 100:,.2f}".removesuffix(".00")


async def _locked_booking(db: AsyncSession, booking_id: str) -> Booking:
    """Holds the booking while its price changes, so that nothing completes or pays it meanwhile."""
    booking = (await db.execute(select(Booking).where(Booking.id == booking_id).with_for_update())).scalar_one_or_none()
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking


def _clear_pending(booking: Booking) -> None:
    booking.pending_extra_id = None
    booking.pending_extra_amount = None
    booking.pending_extra_reason = None


async def _pending_charge(db: AsyncSession, booking: Booking, charge_id: str) -> BookingExtraCharge:
    charge = await db.get(BookingExtraCharge, charge_id)
    if charge is None or charge.booking_id != booking.id:
        raise HTTPException(status_code=404, detail="Extra charge not found")
    if charge.status != PENDING:
        raise HTTPException(status_code=409, detail="This extra charge has already been answered")
    if booking.status not in OPEN_STATUSES:
        charge.status = EXPIRED
        charge.decided_at = _now()
        _clear_pending(booking)
        await db.commit()
        raise HTTPException(
            status_code=409, detail=f"The booking is {booking.status.lower()}, so this no longer applies"
        )
    return charge


def _customer_only(booking: Booking, user: dict) -> None:
    # Not even an admin agrees to pay on a customer's behalf.
    if booking.customer_id != user.get("sub"):
        raise HTTPException(status_code=403, detail="Only the customer can answer this")


@router.get("/bookings/{booking_id}/extra-charges", response_model=List[ExtraChargeResponse])
async def list_extra_charges(
    booking_id: str,
    db: AsyncSession = Depends(get_db, scope="function"),
    current_user: dict = Depends(get_current_user),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
):
    await _visible_booking(db, booking_id, current_user, lookup_owner)
    result = await db.execute(
        select(BookingExtraCharge)
        .where(BookingExtraCharge.booking_id == booking_id)
        .order_by(BookingExtraCharge.created_at.desc())
    )
    return [
        ExtraChargeResponse.model_validate(c).model_copy(update={"reason": masked(c.reason)})
        for c in result.scalars().all()
    ]


@router.post("/bookings/{booking_id}/extra-charges", response_model=BookingResponse, status_code=201)
async def ask_for_extra_charge(
    booking_id: str,
    body: ExtraChargeCreate,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db, scope="function"),
    current_user: dict = Depends(get_current_user),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
    lookup_names: NameLookup = Depends(get_name_lookup),
    notifier: Notifier = Depends(get_notifier),
):
    """The shop or its provider asks the customer to agree to pay more. The price changes only if they do."""
    _, parties = await _visible_booking(db, booking_id, current_user, lookup_owner)
    if not parties & {SHOP_OWNER, PROVIDER, ADMIN}:
        raise HTTPException(status_code=403, detail="Only the shop or its provider can ask for this")
    booking = await _locked_booking(db, booking_id)
    if booking.status not in OPEN_STATUSES:
        raise HTTPException(
            status_code=409, detail=f"The booking is {booking.status.lower()}: nothing can be added now"
        )
    if booking.customer_id.startswith(WALK_IN_PREFIX):
        raise HTTPException(status_code=409, detail="A walk-in has no app to approve this: agree the price with them")
    if booking.payment_status != "UNPAID":
        raise HTTPException(
            status_code=409, detail="This booking is already paid, so an extra charge cannot be added in the app yet"
        )
    if booking.package_purchase_id:
        raise HTTPException(status_code=409, detail="This visit is covered by a prepaid package")
    if booking.pending_extra_id:
        raise HTTPException(status_code=409, detail="The customer has not answered your last request yet")
    charge = BookingExtraCharge(
        id=str(uuid.uuid4()),
        booking_id=booking.id,
        amount_cents=body.amount_cents,
        reason=body.reason,
        status=PENDING,
        requested_by=current_user["sub"],
        created_at=_now(),
    )
    db.add(charge)
    reason = masked(body.reason)
    booking.pending_extra_id = charge.id
    booking.pending_extra_amount = body.amount_cents
    booking.pending_extra_reason = reason
    await db.flush()
    await manager.broadcast(booking.id, {"booking_id": booking.id, "status": booking.status})
    await db.commit()
    background.add_task(
        notify_booking,
        notifier,
        snapshot(booking),
        "booking.extra_requested",
        current_user["sub"],
        lookup_owner,
        roles=("customer",),
        extra={"amount": _rupees(body.amount_cents), "reason": reason},
    )
    return await present(booking, current_user, lookup_names)


async def _told_of_answer(background, notifier, booking, event, actor, lookup_owner, amount) -> None:
    await manager.broadcast(booking.id, {"booking_id": booking.id, "status": booking.status})
    background.add_task(
        notify_booking,
        notifier,
        snapshot(booking),
        event,
        actor,
        lookup_owner,
        roles=("shop", "provider"),
        extra={"amount": _rupees(amount), "new_total": _rupees(booking.total_amount)},
    )


@router.post("/bookings/{booking_id}/extra-charges/{charge_id}/approve", response_model=BookingResponse)
async def approve_extra_charge(
    booking_id: str,
    charge_id: str,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db, scope="function"),
    current_user: dict = Depends(get_current_user),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
    lookup_names: NameLookup = Depends(get_name_lookup),
    notifier: Notifier = Depends(get_notifier),
    close_open_payments: OpenPaymentCloser = Depends(get_open_payment_closer),
):
    """The customer agrees: the booking now costs this much more."""
    await _visible_booking(db, booking_id, current_user, lookup_owner)
    booking = await _locked_booking(db, booking_id)
    _customer_only(booking, current_user)
    charge = await _pending_charge(db, booking, charge_id)
    # A checkout already started would charge the old price, so it goes first. Raises when that cannot be done.
    if await close_open_payments(booking.id):
        booking.payment_status = "PAID"
    if booking.payment_status != "UNPAID":
        charge.status = EXPIRED
        charge.decided_at = _now()
        _clear_pending(booking)
        await db.commit()
        raise HTTPException(
            status_code=409, detail="This booking has just been paid, so the price can no longer change"
        )
    charge.status = APPROVED
    charge.decided_by = current_user["sub"]
    charge.decided_at = _now()
    booking.total_amount += charge.amount_cents
    booking.extra_amount = (booking.extra_amount or 0) + charge.amount_cents
    _clear_pending(booking)
    await db.flush()
    await db.commit()
    await _told_of_answer(
        background, notifier, booking, "booking.extra_approved", current_user["sub"], lookup_owner, charge.amount_cents
    )
    return await present(booking, current_user, lookup_names)


@router.post("/bookings/{booking_id}/extra-charges/{charge_id}/decline", response_model=BookingResponse)
async def decline_extra_charge(
    booking_id: str,
    charge_id: str,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db, scope="function"),
    current_user: dict = Depends(get_current_user),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
    lookup_names: NameLookup = Depends(get_name_lookup),
    notifier: Notifier = Depends(get_notifier),
):
    """The customer says no: the price stays as it was."""
    await _visible_booking(db, booking_id, current_user, lookup_owner)
    booking = await _locked_booking(db, booking_id)
    _customer_only(booking, current_user)
    charge = await _pending_charge(db, booking, charge_id)
    charge.status = DECLINED
    charge.decided_by = current_user["sub"]
    charge.decided_at = _now()
    _clear_pending(booking)
    await db.flush()
    await db.commit()
    await _told_of_answer(
        background, notifier, booking, "booking.extra_declined", current_user["sub"], lookup_owner, charge.amount_cents
    )
    return await present(booking, current_user, lookup_names)


@router.delete("/bookings/{booking_id}/extra-charges/{charge_id}", response_model=BookingResponse)
async def withdraw_extra_charge(
    booking_id: str,
    charge_id: str,
    db: AsyncSession = Depends(get_db, scope="function"),
    current_user: dict = Depends(get_current_user),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
    lookup_names: NameLookup = Depends(get_name_lookup),
):
    """The shop takes back a request the customer has not answered."""
    _, parties = await _visible_booking(db, booking_id, current_user, lookup_owner)
    if not parties & {SHOP_OWNER, PROVIDER, ADMIN}:
        raise HTTPException(status_code=403, detail="Only the shop or its provider can take this back")
    booking = await _locked_booking(db, booking_id)
    charge = await _pending_charge(db, booking, charge_id)
    charge.status = WITHDRAWN
    charge.decided_by = current_user["sub"]
    charge.decided_at = _now()
    _clear_pending(booking)
    await db.flush()
    await db.commit()
    return await present(booking, current_user, lookup_names)
