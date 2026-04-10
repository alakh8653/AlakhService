from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AlreadyExistsException, CredentialsException
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.models.user import User
from app.schemas.user import UserCreate
from app.services.user_service import get_user_by_email


async def authenticate_user(
    db: AsyncSession, email: str, password: str
) -> User | bool:
    """Verify credentials and return the user, or False on failure."""
    user = await get_user_by_email(db, email=email)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


async def register_user(db: AsyncSession, user_create: UserCreate) -> User:
    """Hash the password, persist the new user, and return it."""
    existing = await get_user_by_email(db, email=user_create.email)
    if existing:
        raise AlreadyExistsException(resource_name="User")

    hashed_pw = get_password_hash(user_create.password)
    user = User(
        email=user_create.email,
        hashed_password=hashed_pw,
        full_name=user_create.full_name,
        phone_number=user_create.phone_number,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def get_user_from_token(db: AsyncSession, token: str) -> User | None:
    """Decode a JWT and return the corresponding user."""
    try:
        payload = decode_token(token)
    except CredentialsException:
        return None
    email: str | None = payload.get("sub")
    if email is None:
        return None
    return await get_user_by_email(db, email=email)
