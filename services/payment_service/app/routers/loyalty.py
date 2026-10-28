"""A customer's loyalty points and referral code (see app.services.loyalty_service)."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.services import loyalty_service

router = APIRouter()


class LoyaltyEntryOut(BaseModel):
    kind: str
    points: int
    booking_id: Optional[str] = None
    note: Optional[str] = None
    created_at: str


class LoyaltySummary(BaseModel):
    points: int
    # What the points are worth now, and the rules, for the app to explain them.
    value_cents: int
    point_value_cents: int
    points_per_100_rupees: int
    redeem_max_percent: int
    referral_code: str
    referral_bonus_points: int
    friends_rewarded: int
    friends_pending: int
    referred_by_friend: bool
    history: List[LoyaltyEntryOut]


class UseReferralCode(BaseModel):
    code: str = Field(min_length=4, max_length=12)


@router.get("/loyalty/me", response_model=LoyaltySummary)
async def my_points(db: AsyncSession = Depends(get_db), current_user: dict = Depends(get_current_user)):
    user_id = current_user["sub"]
    points = await loyalty_service.balance(db, user_id)
    rewarded, pending = await loyalty_service.referral_counts(db, user_id)
    return LoyaltySummary(
        points=points,
        value_cents=loyalty_service.points_value_cents(max(points, 0)),
        point_value_cents=settings.LOYALTY_POINT_VALUE_CENTS,
        points_per_100_rupees=settings.LOYALTY_POINTS_PER_100_RUPEES,
        redeem_max_percent=settings.LOYALTY_REDEEM_MAX_PERCENT,
        referral_code=await loyalty_service.code_for(db, user_id),
        referral_bonus_points=settings.REFERRAL_BONUS_POINTS,
        friends_rewarded=rewarded,
        friends_pending=pending,
        referred_by_friend=await loyalty_service.referred_by(db, user_id),
        history=[
            LoyaltyEntryOut(
                kind=e.kind, points=e.points, booking_id=e.booking_id, note=e.note, created_at=e.created_at.isoformat()
            )
            for e in await loyalty_service.history(db, user_id)
        ],
    )


@router.post("/loyalty/referral", status_code=201)
async def use_referral_code(
    body: UseReferralCode, db: AsyncSession = Depends(get_db), current_user: dict = Depends(get_current_user)
):
    """A new customer enters the code of the friend who invited them; both get a bonus after their first
    completed booking."""
    try:
        await loyalty_service.use_code(db, current_user["sub"], body.code)
    except loyalty_service.ReferralRefused as e:
        raise HTTPException(status_code=e.status, detail=str(e)) from e
    return {"message": f"Code added. You both get {settings.REFERRAL_BONUS_POINTS} points after your first booking."}
