from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.security import oauth2_scheme, decode_token
from app.core.exceptions import CredentialsException, PermissionDeniedException
from app.models.user import User
from app.services.user_service import get_user_by_email


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Decode JWT and return the current authenticated user."""
    payload = decode_token(token)
    email: str | None = payload.get("sub")
    if email is None:
        raise CredentialsException()
    user = await get_user_by_email(db, email=email)
    if user is None:
        raise CredentialsException()
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Return the current user only if they are active."""
    if not current_user.is_active:
        raise PermissionDeniedException()
    return current_user


async def get_current_superuser(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Return the current user only if they are a superuser."""
    if not current_user.is_superuser:
        raise PermissionDeniedException()
    return current_user
