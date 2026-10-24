"""In-app chat and masked calls between a booking's customer and its shop.

The platform's rule is that a shop never learns a customer's phone or email (nor the customer a shop
person's own number), so the two talk here: messages have contact details hidden before they are
stored (app/core/contact_filter.py), and calls go through a telephony bridge that rings both sides from
a virtual number (app/core/telephony.py).

Who: the booking's customer, the owner of its shop and the provider assigned to it; admins may read.
When: while the booking is open, and for CHAT_GRACE after it completes or is cancelled; after that the
chat is read-only.
"""

from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import false, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import risk
from app.core.access import ADMIN, CUSTOMER, PROVIDER, SHOP_OWNER, OwnerLookup, relationships
from app.core.contact_filter import mask_contact
from app.core.names import FALLBACK, NameLookup, get_name_lookup
from app.core.notifier import Notifier, get_notifier
from app.core.privacy import CLOSED_STATUSES
from app.core.telephony import CallBridge, CallFailed, NumberLookup, get_call_bridge, get_number_lookup
from app.database import get_db
from app.dependencies import get_clock, get_current_user, get_shop_owner_lookup
from app.models.booking import Booking
from app.models.chat import BookingCall, BookingMessage
from app.schemas.chat import (
    CallResponse,
    FlaggedMessagePage,
    MessageCreate,
    MessagePage,
    MessageResponse,
    ReadReceipt,
    RepeatOffenderList,
)
from app.services.booking_service import ACTIVE_STATUSES, booking_service

router = APIRouter()
log = structlog.get_logger()

# How long after a booking completes or is cancelled its parties can still write (e.g. "left my
# umbrella"); after that the chat is read-only.
CHAT_GRACE = timedelta(hours=24)
# Per sender and booking: a burst limit, and a ceiling for a whole day.
MAX_MESSAGES_PER_MINUTE = 10
MAX_MESSAGES_PER_DAY = 200
# Per caller and booking.
MAX_CALLS_PER_10_MINUTES = 3

SHOP = "shop"
SENDER_NAMES = {SHOP: "Shop", PROVIDER: "Provider"}


def _utc(at: datetime) -> datetime:
    # SQLite hands back naive datetimes; they are stored as UTC.
    return at if at.tzinfo else at.replace(tzinfo=timezone.utc)


def _side(parties: set) -> Optional[str]:
    """The role the caller writes in: customer, shop (owner) or provider; None for an admin only reading."""
    if CUSTOMER in parties:
        return CUSTOMER
    if SHOP_OWNER in parties:
        return SHOP
    if PROVIDER in parties:
        return PROVIDER
    return None


def _open_until(booking: Booking) -> Optional[datetime]:
    if booking.status not in CLOSED_STATUSES:
        return None
    return _utc(booking.updated_at) + CHAT_GRACE


def _is_open(booking: Booking, now: datetime) -> bool:
    until = _open_until(booking)
    return until is None or now <= until


async def _booking_for(db, booking_id: str, user: dict, lookup_owner: OwnerLookup):
    booking = await booking_service.get_booking(db, booking_id)
    parties = await relationships(booking, user, lookup_owner) if booking else set()
    if not parties:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking, parties


def _writer(booking: Booking, parties: set, now: datetime) -> str:
    """The caller's side, if they may write (or call) on this booking right now."""
    side = _side(parties)
    if side is None:
        raise HTTPException(status_code=403, detail="Only the customer and the shop can take part in this chat")
    if not _is_open(booking, now):
        raise HTTPException(status_code=409, detail="This booking is closed; its chat is read-only")
    return side


def _from_other_side(side: Optional[str]):
    """Messages the other side wrote (for an admin: none)."""
    if side == CUSTOMER:
        return BookingMessage.sender_role != CUSTOMER
    if side in (SHOP, PROVIDER):
        return BookingMessage.sender_role == CUSTOMER
    return false()


def _present(message: BookingMessage, user_id: str, customer_name: str) -> MessageResponse:
    return MessageResponse(
        id=message.id,
        booking_id=message.booking_id,
        sender_role=message.sender_role,
        sender_name=customer_name if message.sender_role == CUSTOMER else SENDER_NAMES.get(message.sender_role, "Shop"),
        is_mine=message.sender_id == user_id,
        body=message.body,
        flagged=message.flagged,
        created_at=_utc(message.created_at),
        read_at=_utc(message.read_at) if message.read_at else None,
    )


async def _customer_name(lookup_names: NameLookup, customer_id: str) -> str:
    try:
        return (await lookup_names([customer_id])).get(customer_id, FALLBACK)
    except Exception:
        return FALLBACK


@router.get("/bookings/{booking_id}/messages", response_model=MessagePage)
async def list_messages(
    booking_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
    lookup_names: NameLookup = Depends(get_name_lookup),
    bridge: CallBridge = Depends(get_call_bridge),
    clock: Callable[[], datetime] = Depends(get_clock),
):
    """The booking's chat, newest page first (each page oldest first)."""
    booking, parties = await _booking_for(db, booking_id, current_user, lookup_owner)
    side = _side(parties)
    in_booking = BookingMessage.booking_id == booking_id
    total = (await db.execute(select(func.count()).where(in_booking))).scalar() or 0
    unread = (
        await db.execute(
            select(func.count()).where(in_booking, BookingMessage.read_at.is_(None), _from_other_side(side))
        )
    ).scalar() or 0
    rows = (
        (
            await db.execute(
                select(BookingMessage)
                .where(in_booking)
                .order_by(BookingMessage.created_at.desc(), BookingMessage.id.desc())
                .offset((page - 1) * per_page)
                .limit(per_page)
            )
        )
        .scalars()
        .all()
    )
    name = await _customer_name(lookup_names, booking.customer_id)
    can_send = side is not None and _is_open(booking, clock())
    return MessagePage(
        items=[_present(m, current_user.get("sub"), name) for m in reversed(rows)],
        total=total,
        page=page,
        per_page=per_page,
        unread=unread,
        can_send=can_send,
        open_until=_open_until(booking),
        calling_enabled=bridge.enabled and can_send,
    )


async def _count_since(db, model, column, user_id: str, booking_id: str, since: datetime) -> int:
    return (
        await db.execute(
            select(func.count()).where(model.booking_id == booking_id, column == user_id, model.created_at >= since)
        )
    ).scalar() or 0


async def notify_message(
    notifier: Notifier, lookup_owner: OwnerLookup, booking: dict, sender_side: str, sender_id: str
) -> None:
    """Tells the other side there is a new message (not what it says)."""
    if sender_side == CUSTOMER:
        recipients = []
        if booking["shop_id"]:
            try:
                owner = await lookup_owner(booking["shop_id"])
            except Exception as e:  # shop_service down: still tell the provider
                log.warning("chat_notify_owner_lookup_failed", error=str(e))
                owner = None
            if owner:
                recipients.append({"user_id": owner, "role": SHOP})
        if booking["provider_id"]:
            recipients.append({"user_id": booking["provider_id"], "role": PROVIDER})
    else:
        recipients = [{"user_id": booking["customer_id"], "role": CUSTOMER}]
    seen, unique = {sender_id}, []
    for r in recipients:
        if r["user_id"] not in seen:
            seen.add(r["user_id"])
            unique.append(r)
    await notifier.send(
        "booking.message", unique, {"booking_id": booking["booking_id"], "booking_number": booking["booking_number"]}
    )


@router.post("/bookings/{booking_id}/messages", response_model=MessageResponse, status_code=201)
async def send_message(
    booking_id: str,
    body: MessageCreate,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
    lookup_names: NameLookup = Depends(get_name_lookup),
    notifier: Notifier = Depends(get_notifier),
    clock: Callable[[], datetime] = Depends(get_clock),
):
    """Sends a message to the other side. Phone numbers, emails, UPI handles and messaging-app links are
    replaced with "[hidden for your safety]" and the message is flagged for review."""
    now = clock()
    booking, parties = await _booking_for(db, booking_id, current_user, lookup_owner)
    side = _writer(booking, parties, now)
    user_id = current_user.get("sub")
    sent = BookingMessage.sender_id
    if await _count_since(db, BookingMessage, sent, user_id, booking_id, now - timedelta(minutes=1)) >= (
        MAX_MESSAGES_PER_MINUTE
    ):
        raise HTTPException(status_code=429, detail="You're sending messages too quickly. Please wait a moment.")
    if await _count_since(db, BookingMessage, sent, user_id, booking_id, now - timedelta(days=1)) >= (
        MAX_MESSAGES_PER_DAY
    ):
        raise HTTPException(status_code=429, detail="Daily message limit reached for this booking")

    filtered = mask_contact(body.body)
    # The other side is told only of the first message they have not read yet, not of every one.
    sender_is_customer = side == CUSTOMER
    pending = (
        await db.execute(
            select(func.count()).where(
                BookingMessage.booking_id == booking_id,
                BookingMessage.read_at.is_(None),
                (BookingMessage.sender_role == CUSTOMER)
                if sender_is_customer
                else (BookingMessage.sender_role != CUSTOMER),
            )
        )
    ).scalar() or 0
    message = BookingMessage(
        booking_id=booking_id,
        sender_id=user_id,
        sender_role=side,
        body=filtered.text,
        flagged=filtered.flagged,
        flag_reasons=",".join(filtered.found) or None,
        original_body=body.body if filtered.flagged else None,
        created_at=now,
    )
    db.add(message)
    await db.flush()
    await db.commit()
    if filtered.flagged:
        log.info("chat_contact_hidden", booking_id=booking_id, sender_id=user_id, kinds=filtered.found)
        background.add_task(risk.report_risk, user_id, "contact_sharing_attempt", 0.2, True)
    if not pending:
        snapshot = {
            "booking_id": booking.id,
            "booking_number": booking.booking_number,
            "customer_id": booking.customer_id,
            "provider_id": booking.provider_id,
            "shop_id": booking.shop_id,
        }
        background.add_task(notify_message, notifier, lookup_owner, snapshot, side, user_id)
    return _present(message, user_id, await _customer_name(lookup_names, booking.customer_id))


@router.post("/bookings/{booking_id}/messages/read", response_model=ReadReceipt)
async def mark_read(
    booking_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
    clock: Callable[[], datetime] = Depends(get_clock),
):
    """Marks everything the other side wrote as read (their read receipts). Allowed after the chat closes."""
    _, parties = await _booking_for(db, booking_id, current_user, lookup_owner)
    side = _side(parties)
    if side is None:
        return ReadReceipt(marked=0)  # an admin looking does not count as the party reading
    result = await db.execute(
        update(BookingMessage)
        .where(BookingMessage.booking_id == booking_id, BookingMessage.read_at.is_(None), _from_other_side(side))
        .values(read_at=clock())
    )
    return ReadReceipt(marked=result.rowcount or 0)


@router.post("/bookings/{booking_id}/call", response_model=CallResponse, status_code=202)
async def call(
    booking_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
    lookup_number: NumberLookup = Depends(get_number_lookup),
    bridge: CallBridge = Depends(get_call_bridge),
    clock: Callable[[], datetime] = Depends(get_clock),
):
    """Rings the caller, then connects them to the other side, from the platform's virtual number.

    The customer is put through to the assigned provider while one is on the job, otherwise to the shop
    owner; the shop and provider are put through to the customer. Neither number is ever returned.
    501 when calling is not enabled (CALL_PROVIDER=none): the apps then offer only the chat.
    """
    if not bridge.enabled:
        raise HTTPException(status_code=501, detail="Calling is not enabled. Please use the chat.")
    now = clock()
    booking, parties = await _booking_for(db, booking_id, current_user, lookup_owner)
    side = _writer(booking, parties, now)
    user_id = current_user.get("sub")
    recent = await _count_since(
        db, BookingCall, BookingCall.caller_id, user_id, booking_id, now - timedelta(minutes=10)
    )
    if recent >= MAX_CALLS_PER_10_MINUTES:
        raise HTTPException(status_code=429, detail="Too many calls. Please wait a few minutes or send a message.")

    if side != CUSTOMER:
        callee_role, callee_id = CUSTOMER, booking.customer_id
    elif booking.provider_id and booking.status in ACTIVE_STATUSES:
        callee_role, callee_id = PROVIDER, booking.provider_id
    else:
        callee_role, callee_id = SHOP, await lookup_owner(booking.shop_id) if booking.shop_id else None
    if not callee_id or callee_id == user_id:
        raise HTTPException(status_code=409, detail="There is nobody to call on this booking yet")

    try:
        caller_number = await lookup_number(user_id)
        callee_number = await lookup_number(callee_id)
    except CallFailed as e:
        raise HTTPException(status_code=503, detail="Calling is unavailable right now. Please use the chat.") from e
    if not caller_number:
        raise HTTPException(status_code=409, detail="Add a phone number to your account to make calls")
    if not callee_number:
        raise HTTPException(status_code=409, detail="They can't take calls right now. Please send a message instead.")

    record = BookingCall(
        booking_id=booking_id,
        caller_id=user_id,
        callee_role=callee_role,
        provider=bridge.name,
        status="failed",
        created_at=now,
    )
    try:
        placed = await bridge.connect(caller_number, callee_number, reference=booking.booking_number)
    except CallFailed as e:
        db.add(record)
        await db.commit()
        log.warning("call_failed", booking_id=booking_id, provider=bridge.name, error=str(e))
        raise HTTPException(status_code=502, detail="Could not place the call right now. Please try again.") from e
    record.status = placed.status
    record.provider_call_id = placed.call_id
    db.add(record)
    await db.flush()
    log.info("call_placed", booking_id=booking_id, provider=bridge.name, callee=callee_role)
    return CallResponse(
        status=placed.status,
        call_id=record.id,
        callee=callee_role,
        message="We're calling you now. Pick up to be connected; neither of you sees the other's number.",
    )


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@router.get("/chat-moderation/flagged", response_model=FlaggedMessagePage, dependencies=[Depends(require_admin)])
async def flagged_messages(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    sender_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Messages that had contact details hidden, newest first, with what was originally written."""
    where = [BookingMessage.flagged.is_(True)]
    if sender_id:
        where.append(BookingMessage.sender_id == sender_id)
    total = (await db.execute(select(func.count()).where(*where))).scalar() or 0
    rows = (
        (
            await db.execute(
                select(BookingMessage)
                .where(*where)
                .order_by(BookingMessage.created_at.desc(), BookingMessage.id)
                .offset(skip)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    items = [
        {
            "id": m.id,
            "booking_id": m.booking_id,
            "sender_id": m.sender_id,
            "sender_role": m.sender_role,
            "body": m.body,
            "original_body": m.original_body,
            "flag_reasons": (m.flag_reasons or "").split(",") if m.flag_reasons else [],
            "created_at": _utc(m.created_at),
        }
        for m in rows
    ]
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.get(
    "/chat-moderation/repeat-offenders", response_model=RepeatOffenderList, dependencies=[Depends(require_admin)]
)
async def repeat_offenders(
    min_attempts: int = Query(2, ge=1, le=100),
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    clock: Callable[[], datetime] = Depends(get_clock),
):
    """People who kept trying to share contact details: most attempts first."""
    attempts = func.count(BookingMessage.id)
    rows = (
        await db.execute(
            select(
                BookingMessage.sender_id,
                func.max(BookingMessage.sender_role),
                attempts,
                func.count(func.distinct(BookingMessage.booking_id)),
                func.max(BookingMessage.created_at),
            )
            .where(BookingMessage.flagged.is_(True), BookingMessage.created_at >= clock() - timedelta(days=days))
            .group_by(BookingMessage.sender_id)
            .having(attempts >= min_attempts)
            .order_by(attempts.desc(), func.max(BookingMessage.created_at).desc())
            .limit(200)
        )
    ).all()
    items = [
        {"user_id": uid, "sender_role": role, "attempts": n, "bookings": b, "last_attempt_at": _utc(last)}
        for uid, role, n, b, last in rows
    ]
    return {"min_attempts": min_attempts, "items": items}
