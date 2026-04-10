from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import math

from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.user import (
    UserProfileCreate, UserProfileUpdate, UserProfileResponse,
    UserAddressCreate, UserAddressUpdate, UserAddressResponse,
    UserPreferencesUpdate, UserPreferencesResponse,
    UserDeviceCreate, UserDeviceResponse,
    PaginatedResponse,
)
from app.services.user_service import user_service
from app.models.user import UserProfile
from sqlalchemy import select, func
import structlog

router = APIRouter()
log = structlog.get_logger()


@router.get("/users/me/profile", response_model=UserProfileResponse)
async def get_my_profile(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("sub")
    profile = await user_service.get_profile(db, user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.put("/users/me/profile", response_model=UserProfileResponse)
async def update_my_profile(
    profile_data: UserProfileCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("sub")
    profile = await user_service.create_or_update_profile(db, user_id, profile_data)
    return profile


@router.get("/users/me/addresses", response_model=list[UserAddressResponse])
async def get_my_addresses(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("sub")
    return await user_service.get_addresses(db, user_id)


@router.post("/users/me/addresses", response_model=UserAddressResponse, status_code=201)
async def add_address(
    address_data: UserAddressCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("sub")
    return await user_service.add_address(db, user_id, address_data)


@router.put("/users/me/addresses/{address_id}", response_model=UserAddressResponse)
async def update_address(
    address_id: str,
    data: UserAddressUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("sub")
    address = await user_service.update_address(db, user_id, address_id, data)
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    return address


@router.delete("/users/me/addresses/{address_id}", status_code=204)
async def delete_address(
    address_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("sub")
    deleted = await user_service.delete_address(db, user_id, address_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Address not found")


@router.post("/users/me/addresses/{address_id}/default")
async def set_default_address(
    address_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("sub")
    success = await user_service.set_default_address(db, user_id, address_id)
    if not success:
        raise HTTPException(status_code=404, detail="Address not found")
    return {"message": "Default address updated"}


@router.get("/users/me/preferences", response_model=UserPreferencesResponse)
async def get_preferences(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("sub")
    return await user_service.get_preferences(db, user_id)


@router.put("/users/me/preferences", response_model=UserPreferencesResponse)
async def update_preferences(
    prefs_data: UserPreferencesUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("sub")
    return await user_service.update_preferences(db, user_id, prefs_data)


@router.post("/users/me/devices", response_model=UserDeviceResponse, status_code=201)
async def register_device(
    device_data: UserDeviceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("sub")
    return await user_service.register_device(db, user_id, device_data)


@router.delete("/users/me/devices/{device_id}", status_code=204)
async def deregister_device(
    device_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("sub")
    success = await user_service.deregister_device(db, user_id, device_id)
    if not success:
        raise HTTPException(status_code=404, detail="Device not found")


@router.post("/users/me/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("sub")
    url = await user_service.upload_avatar(db, user_id, file)
    return {"avatar_url": url}


@router.delete("/users/me/account")
async def delete_account(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("sub")
    await user_service.delete_account(db, None, user_id)
    return {"message": "Account deleted successfully"}


@router.get("/users/{user_id}", response_model=UserProfileResponse)
async def get_user_by_id(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    role = current_user.get("role", "user")
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    profile = await user_service.get_profile(db, user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")
    return profile


@router.get("/users", response_model=PaginatedResponse)
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    role = current_user.get("role", "user")
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    count_result = await db.execute(select(func.count()).select_from(UserProfile))
    total = count_result.scalar() or 0

    result = await db.execute(
        select(UserProfile)
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    items = list(result.scalars().all())
    pages = math.ceil(total / per_page) if per_page > 0 else 0

    return PaginatedResponse(items=items, total=total, page=page, per_page=per_page, pages=pages)
