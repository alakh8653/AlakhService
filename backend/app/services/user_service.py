import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.schemas.user import UserUpdate


async def get_user(db: AsyncSession, user_id: uuid.UUID) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundException(resource_name="User")
    return user


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_users(db: AsyncSession, skip: int = 0, limit: int = 20) -> list[User]:
    result = await db.execute(select(User).offset(skip).limit(limit))
    return list(result.scalars().all())


async def update_user(
    db: AsyncSession, user_id: uuid.UUID, user_update: UserUpdate
) -> User:
    user = await get_user(db, user_id)
    update_data = user_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    await db.flush()
    await db.refresh(user)
    return user


async def delete_user(db: AsyncSession, user_id: uuid.UUID) -> None:
    user = await get_user(db, user_id)
    await db.delete(user)
    await db.flush()


async def change_password(
    db: AsyncSession,
    user_id: uuid.UUID,
    old_password: str,
    new_password: str,
) -> User:
    user = await get_user(db, user_id)
    if not verify_password(old_password, user.hashed_password):
        raise ValueError("Old password is incorrect")
    user.hashed_password = get_password_hash(new_password)
    await db.flush()
    await db.refresh(user)
    return user
