"""Customer trust endpoints: extra charges, free fixes, shared visits and SOS (see app/core/trust.py).

Who may do what:
- extra charges: the shop owner or the assigned provider asks; the customer (or an admin) answers; the
  parties and admins read them;
- free fix, share link: the customer;
- SOS: the customer or the assigned provider; admins list the alerts.
Anyone uninvolved is told the booking does not exist, as everywhere else.
"""

import json
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable, List, Optional

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core import availability, queue_hub, trust
from app.core.access import ADMIN, CUSTOMER, PROVIDER, SHOP_OWNER, OwnerLookup
from app.core.fsm import BookingStatus
from app.core.names import FALLBACK, NameLookup, get_name_lookup
from app.core.notifier import Notifier, get_notifier, notify_booking, snapshot, when
from app.core.privacy import present
from app.database import get_db
from app.dependencies import (
    ScheduleLookup,
    get_admin_lookup,
    get_clock,
    get_current_user,
    get_provider_location_lookup,
    get_schedule_lookup,
    get_service_lookup,
    get_shop_name_lookup,
    get_shop_owner_lookup,
)
from app.models.booking import Booking
from app.models.trust import APPROVED, DECLINED, SosAlert
from app.routers.bookings import _ensure_bookable, _visible_booking, manager
from app.schemas.booking import BookingCreate, BookingResponse
from app.schemas.trust import (
    PublicShare,
    QuoteCreate,
    QuoteResponse,
    ReworkRequest,
    ShareResponse,
    SosAlertList,
    SosRequest,
    SosResponse,
)
from app.services.booking_service import booking_service

router = APIRouter()
log = structlog.get_logger()

# The most recipients notification_service takes in one event.
NOTIFY_BATCH = 20


def _now(clock: Callable[[], datetime]) -> datetime:
    at = clock()
    return at.astimezone(timezone.utc) if at.tzinfo else at.replace(tzinfo=timezone.utc)


def _quote(q) -> QuoteResponse:
    return QuoteResponse(
        id=q.id,
        booking_id=q.booking_id,
        status=q.status,
        items=q.items,
        total_cents=q.total_cents,
        note=q.note,
        created_at=q.created_at,
        decided_at=q.decided_at,
    )


# ------------------------------------------------------------------------------------------ extra charges


@router.post("/bookings/{booking_id}/extras", response_model=QuoteResponse, status_code=201)
async def request_extras(
    booking_id: str,
    body: QuoteCreate,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db, scope="function"),
    current_user: dict = Depends(get_current_user),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
    notifier: Notifier = Depends(get_notifier),
    clock: Callable[[], datetime] = Depends(get_clock),
):
    """The shop or its provider asks the customer to approve extra charges; nothing is added until then."""
    booking, parties = await _visible_booking(db, booking_id, current_user, lookup_owner)
    if not parties & {SHOP_OWNER, PROVIDER}:
        raise HTTPException(status_code=403, detail="Only the shop or its provider can ask for extra charges")
    try:
        quote = await trust.create_quote(
            db, booking, [i.model_dump() for i in body.items], body.note, current_user["sub"], _now(clock)
        )
        await db.commit()
    except IntegrityError as e:  # another quote was asked for at the same moment
        await db.rollback()
        raise HTTPException(status_code=409, detail=trust.UNANSWERED_EXTRAS_MESSAGE) from e
    await manager.broadcast(booking_id, {"booking_id": booking_id, "status": booking.status, "extras": "requested"})
    background.add_task(
        notify_booking,
        notifier,
        snapshot(booking),
        "booking.extras_requested",
        current_user["sub"],
        lookup_owner,
        roles=("customer",),
        extra={"quote_id": quote.id, "total": trust.rupees(quote.total_cents)},
    )
    return _quote(quote)


@router.get("/bookings/{booking_id}/extras", response_model=List[QuoteResponse])
async def list_extras(
    booking_id: str,
    db: AsyncSession = Depends(get_db, scope="function"),
    current_user: dict = Depends(get_current_user),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
):
    """The booking's extra-charge quotes, newest first (its parties and admins)."""
    await _visible_booking(db, booking_id, current_user, lookup_owner)
    return [_quote(q) for q in await trust.list_quotes(db, booking_id)]


async def _decide(booking_id, quote_id, decision, background, db, current_user, lookup_owner, notifier, clock):
    booking, parties = await _visible_booking(db, booking_id, current_user, lookup_owner)
    if not parties & {CUSTOMER, ADMIN}:
        raise HTTPException(status_code=403, detail="Only the customer can answer extra charges")
    quote, changed = await trust.decide_quote(db, booking_id, quote_id, decision, current_user["sub"], _now(clock))
    if not changed:
        return _quote(quote)
    await db.commit()
    await manager.broadcast(booking_id, {"booking_id": booking_id, "status": booking.status, "extras": decision})
    background.add_task(
        notify_booking,
        notifier,
        snapshot(booking),
        "booking.extras_decided",
        current_user["sub"],
        lookup_owner,
        roles=("shop", "provider"),
        extra={
            "quote_id": quote.id,
            "decision": decision.lower(),
            "total": trust.rupees(quote.total_cents),
            "booking_total": trust.rupees(booking.total_amount),
        },
    )
    return _quote(quote)


@router.post("/bookings/{booking_id}/extras/{quote_id}/approve", response_model=QuoteResponse)
async def approve_extras(
    booking_id: str,
    quote_id: str,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db, scope="function"),
    current_user: dict = Depends(get_current_user),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
    notifier: Notifier = Depends(get_notifier),
    clock: Callable[[], datetime] = Depends(get_clock),
):
    """The customer agrees: the extras are added to the booking's total (a paid booking then has a balance)."""
    return await _decide(booking_id, quote_id, APPROVED, background, db, current_user, lookup_owner, notifier, clock)


@router.post("/bookings/{booking_id}/extras/{quote_id}/decline", response_model=QuoteResponse)
async def decline_extras(
    booking_id: str,
    quote_id: str,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db, scope="function"),
    current_user: dict = Depends(get_current_user),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
    notifier: Notifier = Depends(get_notifier),
    clock: Callable[[], datetime] = Depends(get_clock),
):
    """The customer says no: the price stays as it was."""
    return await _decide(booking_id, quote_id, DECLINED, background, db, current_user, lookup_owner, notifier, clock)


# ------------------------------------------------------------------------------------------ free fix


@router.post("/bookings/{booking_id}/rework", response_model=BookingResponse, status_code=201)
async def request_rework(
    booking_id: str,
    body: ReworkRequest,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db, scope="function"),
    current_user: dict = Depends(get_current_user),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
    lookup_schedule: ScheduleLookup = Depends(get_schedule_lookup),
    lookup_service: Callable[[str], Awaitable[Optional[dict]]] = Depends(get_service_lookup),
    notifier: Notifier = Depends(get_notifier),
    lookup_names: NameLookup = Depends(get_name_lookup),
    clock: Callable[[], datetime] = Depends(get_clock),
):
    """A free fix of a completed booking, within the shop's guarantee: a new booking at no cost, for the shop
    to confirm. Once per booking."""
    original, parties = await _visible_booking(db, booking_id, current_user, lookup_owner)
    if CUSTOMER not in parties:
        raise HTTPException(status_code=403, detail="Only the customer can ask for a free fix")
    now = _now(clock)
    if original.status != BookingStatus.COMPLETED.value:
        raise HTTPException(status_code=409, detail="A free fix can be asked for once the booking is completed")
    if original.rework_of:
        raise HTTPException(status_code=409, detail="This booking is already a free fix")
    if original.rework_booking_id:
        raise HTTPException(status_code=409, detail="A free fix has already been booked for this booking")
    until = trust.utc(original.guarantee_until)
    if until is None or now > until:
        raise HTTPException(status_code=409, detail=trust.GUARANTEE_ENDED_MESSAGE)
    schedule = availability.Schedule.from_shop_service(
        await lookup_schedule(original.shop_id) if original.shop_id else None
    )
    if not schedule.accepting_bookings:
        raise HTTPException(status_code=409, detail=availability.NOT_ACCEPTING_MESSAGE)
    if body.preferred_at is not None:
        at = trust.utc(body.preferred_at)
        if at < now:
            raise HTTPException(status_code=422, detail="Choose a time in the future")
        await _ensure_bookable(db, original.shop_id, at, original.duration_minutes, lookup_schedule, now)
    else:
        # The shop confirms the fix and can move it; until then it is pencilled in for tomorrow, same hour.
        at = (now + timedelta(days=1)).replace(minute=0, second=0, microsecond=0)
    data = BookingCreate.model_construct(
        service_id=original.service_id,
        shop_id=original.shop_id,
        scheduled_at=at,
        duration_minutes=original.duration_minutes,
        address_id=original.address_id,
        service_mode=original.service_mode,
        item_description=original.item_description,
        notes=f"Free fix: {body.reason}",
        total_amount=0,
    )
    meta = {"rework_of": original.id, "list_price": 0}
    try:
        rework = await booking_service.create_booking(db, current_user["sub"], data, json.dumps(meta), None, None)
        rework.rework_of = original.id
        original.rework_booking_id = rework.id
        original.updated_at = now
        await db.flush()
        await db.commit()
    except IntegrityError as e:  # asked for twice at the same moment
        await db.rollback()
        raise HTTPException(status_code=409, detail="A free fix has already been booked for this booking") from e
    queue_hub.hub.poke(rework.shop_id)
    listing = None
    try:
        listing = await lookup_service(rework.service_id)
    except HTTPException:
        pass
    background.add_task(
        notify_booking,
        notifier,
        snapshot(rework, (listing or {}).get("name")),
        "booking.created",
        current_user["sub"],
        lookup_owner,
        roles=("shop",),
        extra={
            "rework": True,
            "rework_of": original.id,
            "original_booking_number": original.booking_number,
            "rework_line": f"Free fix under your guarantee for booking {original.booking_number}: no charge.",
        },
    )
    return await present(rework, current_user, lookup_names)


# ------------------------------------------------------------------------------------------ shared visit


def share_url(token: str) -> str:
    return f"{settings.SHARE_BASE_URL.rstrip('/')}/s/{token}"


@router.post("/bookings/{booking_id}/share", response_model=ShareResponse)
async def share_booking(
    booking_id: str,
    db: AsyncSession = Depends(get_db, scope="function"),
    current_user: dict = Depends(get_current_user),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
    clock: Callable[[], datetime] = Depends(get_clock),
):
    """A link the customer can send someone they trust to follow the visit (the same link each time)."""
    booking, parties = await _visible_booking(db, booking_id, current_user, lookup_owner)
    if CUSTOMER not in parties:
        raise HTTPException(status_code=403, detail="Only the customer can share this booking")
    now = _now(clock)
    if booking.status in (BookingStatus.CANCELLED.value, BookingStatus.REFUNDED.value):
        raise HTTPException(status_code=409, detail="This booking was cancelled")
    if now >= trust.share_expires_at(booking):
        raise HTTPException(status_code=409, detail="This visit is over")
    share = await trust.share_for(db, booking, current_user["sub"], now)
    await db.commit()
    return ShareResponse(url=share_url(share.token), expires_at=trust.share_expires_at(booking))


def _first_name(display: Optional[str]) -> Optional[str]:
    if not display or display == FALLBACK:
        return None
    return display.split()[0]


@router.get("/public/shares/{token}", response_model=PublicShare)
async def view_share(
    token: str,
    db: AsyncSession = Depends(get_db, scope="function"),
    clock: Callable[[], datetime] = Depends(get_clock),
    lookup_shop_name: Callable[[str], Awaitable[Optional[str]]] = Depends(get_shop_name_lookup),
    lookup_service: Callable[[str], Awaitable[Optional[dict]]] = Depends(get_service_lookup),
    lookup_names: NameLookup = Depends(get_name_lookup),
    lookup_location: Callable[[str], Awaitable[Optional[dict]]] = Depends(get_provider_location_lookup),
):
    """Public (no login): a shared visit's status. No phone, email, full name or address, ever."""
    booking = await trust.shared_booking(db, token, _now(clock))
    if booking is None:
        raise HTTPException(status_code=404, detail="This link has expired or does not exist")
    shop_name = await lookup_shop_name(booking.shop_id) if booking.shop_id else None
    try:
        service_name = ((await lookup_service(booking.service_id)) or {}).get("name")
    except HTTPException:
        service_name = None
    first_name, location = None, None
    if booking.provider_id:
        try:
            first_name = _first_name((await lookup_names([booking.provider_id])).get(booking.provider_id))
        except Exception:  # the page still shows the status
            first_name = None
        if booking.status in trust.LOCATION_STATUSES:
            location = await lookup_location(booking.provider_id)
    return PublicShare(
        shop_name=shop_name,
        service_name=service_name,
        status=booking.status,
        scheduled_at=trust.utc(booking.scheduled_at),
        provider_first_name=first_name,
        provider_location=location,
    )


# ------------------------------------------------------------------------------------------ SOS


async def alert_admins(notifier: Notifier, lookup_admins, data: dict) -> None:
    """safety.sos to every admin (push, and email: notification_service always emails it to admins)."""
    admins = await lookup_admins()
    if not admins:
        log.error("sos_no_admin_to_alert", booking_id=data.get("booking_id"))
        return
    for start in range(0, len(admins), NOTIFY_BATCH):
        recipients = [{"user_id": a, "role": "admin"} for a in admins[start : start + NOTIFY_BATCH]]
        await notifier.send("safety.sos", recipients, data)


@router.post("/bookings/{booking_id}/sos", response_model=SosResponse, status_code=201)
async def raise_sos(
    booking_id: str,
    body: SosRequest,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db, scope="function"),
    current_user: dict = Depends(get_current_user),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
    notifier: Notifier = Depends(get_notifier),
    lookup_admins=Depends(get_admin_lookup),
    clock: Callable[[], datetime] = Depends(get_clock),
):
    """The customer or the provider asks for help: every admin is alerted; the app offers to call 112."""
    booking, parties = await _visible_booking(db, booking_id, current_user, lookup_owner)
    role = "customer" if CUSTOMER in parties else "provider" if PROVIDER in parties else None
    if role is None:
        raise HTTPException(status_code=403, detail="Only the customer or the provider of this booking can raise SOS")
    now = _now(clock)
    alert = await trust.raise_sos(db, booking_id, current_user["sub"], role, body.lat, body.lng, body.note, now)
    await db.commit()
    # Also for whoever watches the logs: an SOS must never go unseen.
    log.error("sos_raised", booking_id=booking_id, alert_id=alert.id, role=role)
    data = {
        "alert_id": alert.id,
        "booking_id": booking.id,
        "booking_number": booking.booking_number,
        "role": role,
        "raised_at": when(now),
        "lat": body.lat,
        "lng": body.lng,
        "location": f"{body.lat:.5f}, {body.lng:.5f}" if body.lat is not None and body.lng is not None else "unknown",
        "note": trust.masked(alert.note),
    }
    background.add_task(alert_admins, notifier, lookup_admins, data)
    return SosResponse(alert_id=alert.id, emergency_number=trust.EMERGENCY_NUMBER)


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@router.get("/admin/safety/sos", response_model=SosAlertList, dependencies=[Depends(require_admin)])
async def list_sos(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    booking_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db, scope="function"),
):
    """SOS alerts, newest first (admins)."""
    query = select(SosAlert, Booking.booking_number).join(Booking, Booking.id == SosAlert.booking_id)
    count = select(func.count()).select_from(SosAlert)
    if booking_id:
        query = query.where(SosAlert.booking_id == booking_id)
        count = count.where(SosAlert.booking_id == booking_id)
    total = await db.scalar(count) or 0
    rows = await db.execute(
        query.order_by(SosAlert.created_at.desc(), SosAlert.id).offset((page - 1) * per_page).limit(per_page)
    )
    items = [
        {
            "id": a.id,
            "booking_id": a.booking_id,
            "booking_number": number,
            "raised_by": a.raised_by,
            "role": a.role,
            "lat": a.lat,
            "lng": a.lng,
            "note": a.note,
            "created_at": a.created_at,
        }
        for a, number in rows.all()
    ]
    return {"items": items, "total": total, "page": page, "per_page": per_page}
