"""Loyalty points and referrals.

Customers earn points on what they pay for completed bookings and spend them on new bookings, up to a
share of the price. The platform pays for points: a booking paid partly with points earns its shop the
full price (see earnings_service.settle_booking). A customer invited with a friend's code gets a bonus,
and so does the friend, once the new customer's first booking is completed.

Every change is a LoyaltyEntry, unique per person, kind and booking, so a repeated report changes nothing.
"""

import secrets
from datetime import datetime, timezone
from typing import List, Optional

import structlog
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.payment import LoyaltyEntry, Referral, ReferralCode

log = structlog.get_logger()

EARN, REDEEM, REDEEM_RETURN, REFERRAL_BONUS, CLAWBACK = "EARN", "REDEEM", "REDEEM_RETURN", "REFERRAL_BONUS", "CLAWBACK"
# Easy to read out and type: no 0/O or 1/I.
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class ReferralRefused(ValueError):
    """A referral code that cannot be used (with the status to answer)."""

    def __init__(self, message: str, status: int):
        super().__init__(message)
        self.status = status


def points_value_cents(points: int) -> int:
    return points * settings.LOYALTY_POINT_VALUE_CENTS


def points_for_payment(paid_cents: int) -> int:
    """Points earned on [paid_cents] paid for a completed booking."""
    return paid_cents * settings.LOYALTY_POINTS_PER_100_RUPEES // 10000


async def balance(db: AsyncSession, user_id: str) -> int:
    result = await db.execute(
        select(func.coalesce(func.sum(LoyaltyEntry.points), 0)).where(LoyaltyEntry.user_id == user_id)
    )
    return int(result.scalar() or 0)


async def history(db: AsyncSession, user_id: str, limit: int = 50) -> List[LoyaltyEntry]:
    result = await db.execute(
        select(LoyaltyEntry)
        .where(LoyaltyEntry.user_id == user_id)
        .order_by(LoyaltyEntry.created_at.desc(), LoyaltyEntry.id)
        .limit(limit)
    )
    return list(result.scalars().all())


async def _entry(db: AsyncSession, user_id: str, kind: str, booking_id: Optional[str]) -> Optional[LoyaltyEntry]:
    result = await db.execute(
        select(LoyaltyEntry).where(
            LoyaltyEntry.user_id == user_id, LoyaltyEntry.kind == kind, LoyaltyEntry.booking_id == booking_id
        )
    )
    return result.scalar_one_or_none()


async def _add(
    db: AsyncSession, user_id: str, kind: str, points: int, booking_id: Optional[str], note: str
) -> Optional[LoyaltyEntry]:
    """Records the entry once; returns it, or the one already there (None when [points] is 0)."""
    existing = await _entry(db, user_id, kind, booking_id)
    if existing is not None or points == 0:
        return existing
    entry = LoyaltyEntry(
        user_id=user_id,
        kind=kind,
        points=points,
        booking_id=booking_id,
        note=note,
        created_at=datetime.now(timezone.utc),
    )
    try:
        async with db.begin_nested():
            db.add(entry)
            await db.flush()
    except IntegrityError:  # the same event reported at the same moment
        return await _entry(db, user_id, kind, booking_id)
    return entry


# ---------------------------------------------------------------- spending on a booking


async def redeem(db: AsyncSession, user_id: str, booking_id: str, price_cents: int) -> int:
    """Spends points on a new booking, up to LOYALTY_REDEEM_MAX_PERCENT of [price_cents]; returns the
    discount in paise. Asking again for the same booking returns what was spent the first time."""
    earlier = await _entry(db, user_id, REDEEM, booking_id)
    if earlier is not None:
        return points_value_cents(-earlier.points)
    cap_cents = price_cents * settings.LOYALTY_REDEEM_MAX_PERCENT // 100
    points = min(await balance(db, user_id), cap_cents // settings.LOYALTY_POINT_VALUE_CENTS)
    if points <= 0:
        return 0
    entry = await _add(db, user_id, REDEEM, -points, booking_id, "Used on a booking")
    return points_value_cents(-entry.points) if entry else 0


async def redeemed_cents(db: AsyncSession, booking_id: str) -> int:
    """What points paid for the booking, net of any returned (the platform's share of its price)."""
    result = await db.execute(
        select(func.coalesce(func.sum(LoyaltyEntry.points), 0)).where(
            LoyaltyEntry.booking_id == booking_id, LoyaltyEntry.kind.in_((REDEEM, REDEEM_RETURN))
        )
    )
    return points_value_cents(-int(result.scalar() or 0))


async def return_points(db: AsyncSession, booking_id: str) -> int:
    """A booking paid partly with points was cancelled (or never made): the points go back. Returns them."""
    result = await db.execute(
        select(LoyaltyEntry).where(LoyaltyEntry.booking_id == booking_id, LoyaltyEntry.kind == REDEEM)
    )
    spent = result.scalar_one_or_none()
    if spent is None:
        return 0
    entry = await _add(db, spent.user_id, REDEEM_RETURN, -spent.points, booking_id, "Booking cancelled")
    return entry.points if entry else 0


# ---------------------------------------------------------------- earning


async def booking_completed(db: AsyncSession, booking_id: str, customer_id: str, paid_cents: int) -> int:
    """Points for what the customer paid, and the referral bonuses if this is their first completed
    booking. Returns the points earned (0 when already recorded)."""
    is_first = (
        await db.execute(
            select(func.count()).where(
                LoyaltyEntry.user_id == customer_id, LoyaltyEntry.kind == EARN, LoyaltyEntry.booking_id != booking_id
            )
        )
    ).scalar() == 0
    entry = await _add(db, customer_id, EARN, points_for_payment(paid_cents), booking_id, "Completed booking")
    if is_first:
        await _reward_referral(db, customer_id, booking_id)
    return entry.points if entry else 0


async def _reward_referral(db: AsyncSession, referee_id: str, booking_id: str) -> None:
    referral = await db.get(Referral, referee_id)
    if referral is None or referral.rewarded_at is not None:
        return
    bonus = settings.REFERRAL_BONUS_POINTS
    await _add(db, referee_id, REFERRAL_BONUS, bonus, booking_id, "Welcome bonus for joining with a friend's code")
    rewarded = (
        await db.execute(
            select(func.count()).where(Referral.referrer_id == referral.referrer_id, Referral.rewarded_at.is_not(None))
        )
    ).scalar()
    if rewarded < settings.REFERRALS_MAX_REWARDED:
        await _add(db, referral.referrer_id, REFERRAL_BONUS, bonus, booking_id, "A friend you invited booked")
    referral.rewarded_at = datetime.now(timezone.utc)
    referral.rewarded_booking_id = booking_id
    await db.flush()
    log.info("referral_rewarded", referee_id=referee_id, referrer_id=referral.referrer_id, booking_id=booking_id)


async def booking_refunded_in_full(db: AsyncSession, booking_id: str) -> None:
    """Points earned on a booking that was then refunded in full are taken back."""
    result = await db.execute(
        select(LoyaltyEntry).where(LoyaltyEntry.booking_id == booking_id, LoyaltyEntry.kind == EARN)
    )
    for earned in result.scalars().all():
        await _add(db, earned.user_id, CLAWBACK, -earned.points, booking_id, "Booking refunded")


# ---------------------------------------------------------------- referral codes


async def code_for(db: AsyncSession, user_id: str) -> str:
    """The customer's own referral code, made the first time it is asked for."""
    existing = await db.get(ReferralCode, user_id)
    if existing is not None:
        return existing.code
    for _ in range(10):
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))
        try:
            async with db.begin_nested():
                db.add(ReferralCode(user_id=user_id, code=code, created_at=datetime.now(timezone.utc)))
                await db.flush()
            return code
        except IntegrityError:  # taken (or made for this user at the same moment)
            again = await db.get(ReferralCode, user_id)
            if again is not None:
                return again.code
    raise RuntimeError("Could not make a referral code")


async def use_code(db: AsyncSession, user_id: str, code: str) -> str:
    """Records that [user_id] joined with a friend's [code]; returns the friend's id.

    Only a customer with no completed booking yet can use one, once, and never their own.
    """
    owner = (
        await db.execute(select(ReferralCode).where(ReferralCode.code == code.strip().upper()))
    ).scalar_one_or_none()
    if owner is None:
        raise ReferralRefused("That referral code was not found", 404)
    if owner.user_id == user_id:
        raise ReferralRefused("You cannot use your own referral code", 422)
    if await db.get(Referral, user_id) is not None:
        raise ReferralRefused("You have already used a referral code", 409)
    booked = (
        await db.execute(select(func.count()).where(LoyaltyEntry.user_id == user_id, LoyaltyEntry.kind == EARN))
    ).scalar()
    if booked:
        raise ReferralRefused("Referral codes are for new customers, before their first booking", 409)
    try:
        async with db.begin_nested():
            db.add(Referral(referee_id=user_id, referrer_id=owner.user_id, created_at=datetime.now(timezone.utc)))
            await db.flush()
    except IntegrityError as e:
        raise ReferralRefused("You have already used a referral code", 409) from e
    return owner.user_id


async def referral_counts(db: AsyncSession, user_id: str) -> tuple[int, int]:
    """(friends who joined and booked, friends who joined and have not booked yet)."""
    rows = (await db.execute(select(Referral.rewarded_at).where(Referral.referrer_id == user_id))).scalars().all()
    rewarded = sum(1 for r in rows if r is not None)
    return rewarded, len(rows) - rewarded


async def referred_by(db: AsyncSession, user_id: str) -> bool:
    return await db.get(Referral, user_id) is not None
