"""Customer trust: the start code, free fixes, shared visits and SOS.

- Start code: a home visit or a pickup starts only with the 4-digit code the customer gives the
  professional at the door, so "work started" cannot be marked from somewhere else. Wrong tries are
  counted: after MAX_START_CODE_TRIES in START_CODE_WINDOW the booking refuses more for a while.
- Free fix (rework): within the shop's guarantee_days after completion, once per booking, at no cost.
- Shared visit: a link (no login) showing the visit's status and, while on the way, where the
  professional is, without anyone's contact details.
- SOS: alerts every admin; at most MAX_SOS_ALERTS per booking per SOS_WINDOW.
"""

import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.contact_filter import mask_contact
from app.core.fsm import AT_HOME, PICKUP_DROP, BookingStatus, booking_fsm, mode_problem
from app.models.booking import Booking
from app.models.trust import BookingShare, SosAlert

START_CODE_MESSAGE = "Ask the customer for the 4-digit start code"
MAX_START_CODE_TRIES = 5
START_CODE_WINDOW = timedelta(minutes=15)

DEFAULT_GUARANTEE_DAYS = 7
GUARANTEE_ENDED_MESSAGE = "The free-fix period for this booking has ended"

# A shared link works until this long after the visit's scheduled time.
SHARE_VALID_AFTER = timedelta(hours=24)
# The professional's position is shown only while they are travelling (to the customer, or back to them).
LOCATION_STATUSES = {BookingStatus.PROVIDER_EN_ROUTE.value, BookingStatus.OUT_FOR_DELIVERY.value}

MAX_SOS_ALERTS = 3
SOS_WINDOW = timedelta(minutes=10)
EMERGENCY_NUMBER = "112"


def utc(at: Optional[datetime]) -> Optional[datetime]:
    # SQLite hands back naive datetimes; they are stored as UTC.
    if at is None:
        return None
    return at if at.tzinfo else at.replace(tzinfo=timezone.utc)


def masked(text: Optional[str]) -> Optional[str]:
    return mask_contact(text).text if text else text


async def _locked_booking(db: AsyncSession, booking_id: str) -> Booking:
    """The booking, re-read and locked until the transaction ends (PostgreSQL; SQLite has one writer)."""
    query = select(Booking).where(Booking.id == booking_id).execution_options(populate_existing=True)
    if db.get_bind().dialect.name == "postgresql":
        query = query.with_for_update()
    return (await db.execute(query)).scalar_one()


# ------------------------------------------------------------------------------------------ start code


def new_start_code() -> str:
    return f"{secrets.randbelow(10000):04d}"


def needs_start_code(booking: Booking, target: str) -> bool:
    """Whether moving [booking] to [target] starts the work at the customer's: a home visit starting, or a
    pickup being collected. Only for a move that is otherwise valid, so a wrong one does not cost a try."""
    if not booking.start_code:
        return False
    starting = (booking.service_mode == AT_HOME and target == BookingStatus.IN_PROGRESS.value) or (
        booking.service_mode == PICKUP_DROP and target == BookingStatus.PICKED_UP.value
    )
    if not starting:
        return False
    source, to = BookingStatus(booking.status), BookingStatus(target)
    return booking_fsm.can_transition(source, to) and mode_problem(booking.service_mode, source, to) is None


async def check_start_code(db: AsyncSession, booking_id: str, code: Optional[str], now: datetime) -> None:
    """Lets the caller go on with the right code; otherwise counts the try (committed) and refuses it."""
    booking = await _locked_booking(db, booking_id)
    since = utc(booking.start_code_tries_since)
    in_window = since is not None and now - since < START_CODE_WINDOW
    if in_window and booking.start_code_tries >= MAX_START_CODE_TRIES:
        wait = max(int((since + START_CODE_WINDOW - now).total_seconds() // 60) + 1, 1)
        raise HTTPException(
            status_code=429,
            detail=f"Too many wrong start codes. Try again in {wait} minutes.",
            headers={"Retry-After": str(wait * 60)},
        )
    if code and hmac.compare_digest(code.strip().encode(), booking.start_code.encode()):
        booking.start_code_tries = 0
        booking.start_code_tries_since = None
        return
    if in_window:
        booking.start_code_tries += 1
    else:
        booking.start_code_tries = 1
        booking.start_code_tries_since = now
    # Kept although the request fails: the next wrong guess must see this one.
    await db.commit()
    raise HTTPException(status_code=422, detail=START_CODE_MESSAGE)


# ------------------------------------------------------------------------------------------ guarantee


def guarantee_days_of(schedule: Optional[dict]) -> int:
    days = (schedule or {}).get("guarantee_days")
    return DEFAULT_GUARANTEE_DAYS if not isinstance(days, int) or days < 0 else days


def stamp_guarantee(booking: Booking, days: int, now: datetime) -> None:
    """Sets until when the customer can ask for a free fix, the first time the booking is completed."""
    if booking.guarantee_until is None:
        booking.guarantee_until = now + timedelta(days=days)


# ------------------------------------------------------------------------------------------ shares


def share_expires_at(booking: Booking) -> datetime:
    return utc(booking.scheduled_at) + SHARE_VALID_AFTER


async def share_for(db: AsyncSession, booking: Booking, user_id: str, now: datetime) -> BookingShare:
    """The booking's share link, made the first time and the same one after that."""
    expires = share_expires_at(booking)
    share = (await db.execute(select(BookingShare).where(BookingShare.booking_id == booking.id))).scalar_one_or_none()
    if share is None:
        share = BookingShare(
            id=str(uuid.uuid4()),
            booking_id=booking.id,
            token=secrets.token_urlsafe(24),
            created_by=user_id,
            created_at=now,
            expires_at=expires,
        )
        db.add(share)
    else:
        share.expires_at = expires  # follows a rescheduled visit
    await db.flush()
    return share


async def shared_booking(db: AsyncSession, token: str, now: datetime) -> Optional[Booking]:
    """The booking a live link is for, or None for an unknown or expired one."""
    if not token or len(token) > 64:
        return None
    share = (await db.execute(select(BookingShare).where(BookingShare.token == token))).scalar_one_or_none()
    if share is None:
        return None
    booking = await db.get(Booking, share.booking_id)
    if booking is None or now >= share_expires_at(booking):
        return None
    return booking


# ------------------------------------------------------------------------------------------ SOS


async def raise_sos(
    db: AsyncSession,
    booking_id: str,
    user_id: str,
    role: str,
    lat: Optional[float],
    lng: Optional[float],
    note: Optional[str],
    now: datetime,
) -> SosAlert:
    await _locked_booking(db, booking_id)  # alerts for one booking are counted one at a time
    recent = await db.scalar(
        select(func.count())
        .select_from(SosAlert)
        .where(SosAlert.booking_id == booking_id, SosAlert.created_at > now - SOS_WINDOW)
    )
    if recent >= MAX_SOS_ALERTS:
        raise HTTPException(
            status_code=429,
            detail=f"Help has already been alerted. If you are in danger, call {EMERGENCY_NUMBER} now.",
        )
    alert = SosAlert(
        id=str(uuid.uuid4()),
        booking_id=booking_id,
        raised_by=user_id,
        role=role,
        lat=lat,
        lng=lng,
        note=note.strip() if note and note.strip() else None,
        created_at=now,
    )
    db.add(alert)
    await db.flush()
    return alert
