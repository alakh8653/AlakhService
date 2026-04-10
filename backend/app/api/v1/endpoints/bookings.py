from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_active_user, get_current_superuser
from app.models.user import User
from app.schemas.booking import BookingCreate, BookingRead, BookingUpdate
from app.services.booking_service import (
    create_booking,
    get_booking,
    get_user_bookings,
    update_booking,
    cancel_booking,
    confirm_booking,
)
from app.api.v1.dependencies import pagination_params

router = APIRouter()


@router.get("/", response_model=list[BookingRead])
async def list_bookings(
    pagination: dict = Depends(pagination_params),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """List all bookings for the current user."""
    return await get_user_bookings(
        db, user_id=current_user.id, skip=pagination["skip"], limit=pagination["limit"]
    )


@router.post("/", response_model=BookingRead, status_code=status.HTTP_201_CREATED)
async def new_booking(
    booking_create: BookingCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new booking for the current user."""
    return await create_booking(db, user_id=current_user.id, booking_create=booking_create)


@router.get("/{booking_id}", response_model=BookingRead)
async def get_booking_detail(
    booking_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get details for a specific booking."""
    return await get_booking(db, booking_id=booking_id)


@router.put("/{booking_id}", response_model=BookingRead)
async def modify_booking(
    booking_id: UUID,
    booking_update: BookingUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a booking's details."""
    return await update_booking(db, booking_id=booking_id, booking_update=booking_update)


@router.delete("/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_booking_endpoint(
    booking_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a booking."""
    await cancel_booking(db, booking_id=booking_id, user_id=current_user.id)


@router.post("/{booking_id}/confirm", response_model=BookingRead)
async def confirm_booking_endpoint(
    booking_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
):
    """Confirm a booking (admin only)."""
    return await confirm_booking(db, booking_id=booking_id)
