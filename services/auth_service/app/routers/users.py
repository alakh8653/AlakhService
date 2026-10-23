"""Account administration: admins look users up; admin_service switches accounts on and off."""

import hmac
import secrets
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import httpx
import redis.asyncio as aioredis
import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import OTPRateLimitedError
from app.core.security import create_access_token, hash_password, verify_password
from app.database import get_db
from app.dependencies import get_current_user, get_redis, security
from app.models.user import User
from app.schemas.auth import AccountDeletionByOTP, UserResponse
from app.services.auth_service import auth_service

router = APIRouter()
internal_router = APIRouter()
log = structlog.get_logger()


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@router.get("/auth/users", response_model=List[UserResponse], dependencies=[Depends(require_admin)])
async def search_users(
    q: Optional[str] = Query(None, description="Part of a name, email or phone number"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(User).order_by(User.created_at.desc()).offset(skip).limit(limit)
    if q and q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(User.full_name.ilike(like), User.email.ilike(like), User.phone.ilike(like), User.id == q.strip())
        )
    return list((await db.execute(stmt)).scalars().all())


class AccountDeletion(BaseModel):
    password: str


async def erase_profile(token: str) -> None:
    """Erases the person's profile, addresses and devices in user_service, acting as them."""
    try:
        async with httpx.AsyncClient(base_url=settings.USER_SERVICE_URL, timeout=10.0) as client:
            resp = await client.delete("/api/v1/users/me/account", headers={"Authorization": f"Bearer {token}"})
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail="Could not delete your account right now. Please try again.") from e
    if resp.status_code >= 400:
        raise HTTPException(status_code=503, detail="Could not delete your account right now. Please try again.")


def get_profile_eraser():
    return erase_profile


async def anonymise_account(db: AsyncSession, redis, user: User, token: str, erase) -> None:
    """Erases the person's profile data, then anonymises the sign-in, so the email/phone are free and
    the account can never be used again. Bookings and payments stay, under the anonymous id, for the
    other party's records (and the law's: invoices are kept for 8 years)."""
    # Profile first: if that fails nothing has changed and the person can simply retry.
    await erase(token)
    user.email = None
    user.phone = None
    user.full_name = "Deleted user"
    user.is_active = False
    user.is_verified = False
    user.hashed_password = hash_password(secrets.token_urlsafe(32))
    user.updated_at = datetime.now(timezone.utc)
    await auth_service.revoke_all_sessions(db, redis, user.id)
    log.info("account_deleted", user_id=user.id)


@router.post("/auth/delete-account")
async def delete_account(
    body: AccountDeletion,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    current_user: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    erase=Depends(get_profile_eraser),
):
    """Deletes the caller's account (password required). See anonymise_account."""
    user = await db.get(User, current_user["sub"])
    if user is None or not user.is_active:
        raise HTTPException(status_code=404, detail="User not found")
    if not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect password")
    await anonymise_account(db, redis, user, credentials.credentials, erase)
    return {"message": "Your account has been deleted"}


@router.post("/auth/delete-account/otp")
async def delete_account_with_code(
    body: AccountDeletionByOTP,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    erase=Depends(get_profile_eraser),
):
    """Deletes an account without signing in, for the web page app stores require
    (https://<DOMAIN>/delete-account): first POST /auth/send-otp with purpose "delete_account",
    then send the code here. Limited per email/phone, and each code allows 5 guesses."""
    key = f"auth:delete_account_attempts:{body.phone_or_email}"
    attempts = await redis.incr(key)
    if attempts == 1:
        await redis.expire(key, settings.DELETE_ACCOUNT_WINDOW_SECONDS)
    if attempts > settings.DELETE_ACCOUNT_ATTEMPTS_PER_WINDOW:
        raise OTPRateLimitedError("Too many attempts. Please try again later.")
    user = await auth_service.verify_otp(db, body)
    # A short-lived token so user_service erases the profile as the person themselves.
    token = create_access_token({"sub": str(user.id), "role": user.role}, timedelta(minutes=2))
    await anonymise_account(db, redis, user, token, erase)
    await redis.delete(key)
    return {"message": "Your account has been deleted"}


def require_internal(x_internal_key: Optional[str] = Header(None)) -> None:
    if not settings.INTERNAL_API_KEY:
        raise HTTPException(status_code=503, detail="Internal API is not configured")
    if not x_internal_key or not hmac.compare_digest(x_internal_key, settings.INTERNAL_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid internal key")


class AccountStatus(BaseModel):
    is_active: bool


@internal_router.post(
    "/internal/users/{user_id}/status", response_model=UserResponse, dependencies=[Depends(require_internal)]
)
async def set_account_status(
    user_id: str,
    body: AccountStatus,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """Bans and unbans. A deactivated account cannot sign in or refresh, and its sessions are ended
    at once (its access tokens are refused at the gateway too)."""
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = body.is_active
    if not body.is_active:
        await auth_service.revoke_all_sessions(db, redis, user_id)
    await db.flush()
    await db.refresh(user)
    return user


# What the other party is shown instead of someone's name when there is nothing usable to show.
DISPLAY_NAME_FALLBACK = "Customer"


def _is_name_part(word: str) -> bool:
    """Letters in any script (with their vowel signs), and the odd hyphen, apostrophe or dot ("D'Souza", "K.")."""
    return word[0].isalpha() and all(c.isalpha() or unicodedata.category(c)[0] == "M" or c in "'.-" for c in word)


def display_name(full_name: Optional[str], is_active: bool = True) -> str:
    """First name and the last name's initial ("Ravi S."), as ride apps show a rider to a driver.

    A name with digits or an "@" in it (someone typing their number or email as their name) is not
    shown at all: the point is that the other party never learns how to reach the person directly.
    """
    parts = (full_name or "").split()
    if not is_active or not parts or not all(_is_name_part(p) for p in parts):
        return DISPLAY_NAME_FALLBACK
    first = parts[0].rstrip(".")[:20]
    first = first[:1].upper() + first[1:]
    if len(parts) == 1:
        return first
    return f"{first} {parts[-1][0].upper()}."


class DisplayNamesRequest(BaseModel):
    user_ids: List[str] = Field(..., max_length=200)


class DisplayNamesResponse(BaseModel):
    # Only the display name: never the email, phone or full name.
    names: Dict[str, str]


@internal_router.post(
    "/internal/users/display-names", response_model=DisplayNamesResponse, dependencies=[Depends(require_internal)]
)
async def display_names(body: DisplayNamesRequest, db: AsyncSession = Depends(get_db)):
    """Names other services may show to the other party of a booking (e.g. a shop seeing its customers).

    Every id asked for gets an answer; one that matches no account reads "Customer".
    """
    ids = list(dict.fromkeys(i for i in body.user_ids if i))
    found = {}
    if ids:
        rows = await db.execute(select(User.id, User.full_name, User.is_active).where(User.id.in_(ids)))
        found = {uid: display_name(name, active) for uid, name, active in rows.all()}
    return {"names": {uid: found.get(uid, DISPLAY_NAME_FALLBACK) for uid in ids}}


class CallContact(BaseModel):
    phone: Optional[str] = None


@internal_router.get(
    "/internal/users/{user_id}/call-contact", response_model=CallContact, dependencies=[Depends(require_internal)]
)
async def call_contact(user_id: str, db: AsyncSession = Depends(get_db)):
    """The number a masked call rings (booking_service's call bridge). Never passed on to the other party."""
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=404, detail="User not found")
    return {"phone": user.phone}
