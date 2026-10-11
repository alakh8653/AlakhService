"""Account administration: admins look users up; admin_service switches accounts on and off."""

import hmac
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
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
