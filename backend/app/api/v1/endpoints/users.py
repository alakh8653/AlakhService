from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_active_user, get_current_superuser
from app.models.user import User
from app.schemas.user import UserRead, UserUpdate
from app.services.user_service import get_user, get_users, update_user, delete_user
from app.api.v1.dependencies import pagination_params

router = APIRouter()


@router.get("/me", response_model=UserRead)
async def get_me(current_user: User = Depends(get_current_active_user)):
    """Return the currently authenticated user's profile."""
    return current_user


@router.put("/me", response_model=UserRead)
async def update_me(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the currently authenticated user's profile."""
    return await update_user(db, current_user.id, user_update)


@router.get("/{user_id}", response_model=UserRead)
async def get_user_by_id(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
):
    """Get a user by ID (admin only)."""
    return await get_user(db, user_id)


@router.get("/", response_model=list[UserRead])
async def list_users(
    pagination: dict = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
):
    """List all users with pagination (admin only)."""
    return await get_users(db, skip=pagination["skip"], limit=pagination["limit"])


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
):
    """Delete a user by ID (admin only)."""
    await delete_user(db, user_id)
