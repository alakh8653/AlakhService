from uuid import UUID
from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_active_user
from app.models.user import User
from app.services.booking_service import get_booking
from app.core.exceptions import PermissionDeniedException


def pagination_params(
    skip: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=20, ge=1, le=100, description="Maximum records to return"),
) -> dict:
    """Reusable pagination dependency."""
    return {"skip": skip, "limit": limit}


def common_filters(
    search: str | None = Query(default=None, description="Full-text search term"),
    is_active: bool | None = Query(default=None, description="Filter by active status"),
) -> dict:
    """Reusable query filter dependency."""
    return {"search": search, "is_active": is_active}


async def verify_booking_ownership(
    booking_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Ensure the current user owns the given booking (or is a superuser)."""
    booking = await get_booking(db, booking_id=booking_id)
    if not current_user.is_superuser and booking.user_id != current_user.id:
        raise PermissionDeniedException()
    return booking
