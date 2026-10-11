"""Account administration: admins look users up; admin_service switches accounts on and off."""

import hmac
import secrets
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import hash_password, verify_password
from app.database import get_db
from app.dependencies import get_current_user, security
from app.models.user import RefreshToken, User
from app.schemas.auth import UserResponse

router = APIRouter()
internal_router = APIRouter()


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
        stmt = stmt.where(or_(User.full_name.ilike(like), User.email.ilike(like), User.phone.ilike(like), User.id == q.strip()))
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


@router.post("/auth/delete-account")
async def delete_account(
    body: AccountDeletion,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    erase=Depends(get_profile_eraser),
):
    """Deletes the caller's account (password required): their profile data is erased and the
    sign-in is anonymised, so the email/phone are free and the account can never be used again.
    Bookings and payments stay, under the anonymous id, for the other party's records."""
    user = await db.get(User, current_user["sub"])
    if user is None or not user.is_active:
        raise HTTPException(status_code=404, detail="User not found")
    if not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect password")
    # Profile first: if that fails nothing has changed and the person can simply retry.
    await erase(credentials.credentials)
    user.email = None
    user.phone = None
    user.full_name = "Deleted user"
    user.is_active = False
    user.is_verified = False
    user.hashed_password = hash_password(secrets.token_urlsafe(32))
    await db.execute(
        update(RefreshToken).where(RefreshToken.user_id == user.id, RefreshToken.is_revoked == False).values(is_revoked=True)  # noqa: E712
    )
    await db.flush()
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
async def set_account_status(user_id: str, body: AccountStatus, db: AsyncSession = Depends(get_db)):
    """Bans and unbans. A deactivated account cannot sign in or refresh, and its sessions are ended."""
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = body.is_active
    if not body.is_active:
        await db.execute(
            update(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.is_revoked == False).values(is_revoked=True)  # noqa: E712
        )
    await db.flush()
    await db.refresh(user)
    return user
