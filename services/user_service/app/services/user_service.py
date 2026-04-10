import hashlib
import uuid
from datetime import datetime, timezone
from typing import List, Optional
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_
from fastapi import UploadFile, HTTPException

from app.models.user import UserProfile, UserAddress, UserPreferences, UserDevice
from app.schemas.user import (
    UserProfileCreate, UserAddressCreate, UserAddressUpdate,
    UserPreferencesUpdate, UserDeviceCreate,
)

log = structlog.get_logger()


class UserService:

    async def get_profile(self, db: AsyncSession, user_id: str) -> Optional[UserProfile]:
        result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
        return result.scalar_one_or_none()

    async def create_or_update_profile(self, db: AsyncSession, user_id: str, profile_data: UserProfileCreate) -> UserProfile:
        result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
        profile = result.scalar_one_or_none()

        now = datetime.now(timezone.utc)
        update_dict = profile_data.model_dump(exclude_unset=True)

        if profile:
            for key, value in update_dict.items():
                setattr(profile, key, value)
            profile.updated_at = now
        else:
            profile = UserProfile(
                id=str(uuid.uuid4()),
                user_id=user_id,
                created_at=now,
                updated_at=now,
                **update_dict,
            )
            db.add(profile)
        await db.flush()
        return profile

    async def get_addresses(self, db: AsyncSession, user_id: str) -> List[UserAddress]:
        result = await db.execute(select(UserAddress).where(UserAddress.user_id == user_id))
        return list(result.scalars().all())

    async def add_address(self, db: AsyncSession, user_id: str, address_data: UserAddressCreate) -> UserAddress:
        addresses = await self.get_addresses(db, user_id)
        is_default = len(addresses) == 0

        address = UserAddress(
            id=str(uuid.uuid4()),
            user_id=user_id,
            is_default=is_default,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            **address_data.model_dump(),
        )
        db.add(address)
        await db.flush()
        return address

    async def update_address(self, db: AsyncSession, user_id: str, address_id: str, data: UserAddressUpdate) -> Optional[UserAddress]:
        result = await db.execute(
            select(UserAddress).where(and_(UserAddress.id == address_id, UserAddress.user_id == user_id))
        )
        address = result.scalar_one_or_none()
        if not address:
            return None

        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(address, key, value)
        address.updated_at = datetime.now(timezone.utc)
        await db.flush()
        return address

    async def delete_address(self, db: AsyncSession, user_id: str, address_id: str) -> bool:
        result = await db.execute(
            select(UserAddress).where(and_(UserAddress.id == address_id, UserAddress.user_id == user_id))
        )
        address = result.scalar_one_or_none()
        if not address:
            return False
        await db.delete(address)
        await db.flush()
        return True

    async def set_default_address(self, db: AsyncSession, user_id: str, address_id: str) -> bool:
        await db.execute(
            update(UserAddress)
            .where(UserAddress.user_id == user_id)
            .values(is_default=False)
        )
        result = await db.execute(
            select(UserAddress).where(and_(UserAddress.id == address_id, UserAddress.user_id == user_id))
        )
        address = result.scalar_one_or_none()
        if not address:
            await db.flush()
            return False
        address.is_default = True
        await db.flush()
        return True

    async def get_preferences(self, db: AsyncSession, user_id: str) -> UserPreferences:
        result = await db.execute(select(UserPreferences).where(UserPreferences.user_id == user_id))
        prefs = result.scalar_one_or_none()
        if not prefs:
            prefs = UserPreferences(
                id=str(uuid.uuid4()),
                user_id=user_id,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(prefs)
            await db.flush()
        return prefs

    async def update_preferences(self, db: AsyncSession, user_id: str, prefs_data: UserPreferencesUpdate) -> UserPreferences:
        prefs = await self.get_preferences(db, user_id)
        for key, value in prefs_data.model_dump(exclude_unset=True).items():
            setattr(prefs, key, value)
        prefs.updated_at = datetime.now(timezone.utc)
        await db.flush()
        return prefs

    async def register_device(self, db: AsyncSession, user_id: str, device_data: UserDeviceCreate) -> UserDevice:
        result = await db.execute(
            select(UserDevice).where(UserDevice.device_id == device_data.device_id)
        )
        existing = result.scalar_one_or_none()

        now = datetime.now(timezone.utc)
        if existing:
            existing.device_token = device_data.device_token
            existing.user_id = user_id
            existing.is_active = True
            existing.last_seen = now
            await db.flush()
            return existing

        device = UserDevice(
            id=str(uuid.uuid4()),
            user_id=user_id,
            device_token=device_data.device_token,
            platform=device_data.platform,
            device_id=device_data.device_id,
            is_active=True,
            last_seen=now,
            created_at=now,
        )
        db.add(device)
        await db.flush()
        return device

    async def deregister_device(self, db: AsyncSession, user_id: str, device_id: str) -> bool:
        result = await db.execute(
            select(UserDevice).where(and_(UserDevice.device_id == device_id, UserDevice.user_id == user_id))
        )
        device = result.scalar_one_or_none()
        if not device:
            return False
        device.is_active = False
        await db.flush()
        return True

    async def get_active_devices(self, db: AsyncSession, user_id: str) -> List[UserDevice]:
        result = await db.execute(
            select(UserDevice).where(and_(UserDevice.user_id == user_id, UserDevice.is_active))
        )
        return list(result.scalars().all())

    async def upload_avatar(self, db: AsyncSession, user_id: str, file: UploadFile) -> str:
        allowed_content_types = {
            "image/jpeg": "jpg",
            "image/png": "png",
            "image/webp": "webp",
        }
        if file.content_type not in allowed_content_types:
            raise HTTPException(status_code=400, detail="Invalid image type")

        contents = await file.read()
        if len(contents) > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large (max 5MB)")

        # Derive extension from validated content_type (not from user-supplied filename)
        ext = allowed_content_types[file.content_type]
        safe_filename = f"{uuid.uuid4()}.{ext}"
        # NOTE: In production this URL is the S3 object key after uploading `contents`
        # to the configured S3_BUCKET. Here we store the path reference only.
        avatar_url = f"/avatars/{user_id}/{safe_filename}"

        result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
        profile = result.scalar_one_or_none()
        if profile:
            profile.avatar_url = avatar_url
            profile.updated_at = datetime.now(timezone.utc)
        else:
            profile = UserProfile(
                id=str(uuid.uuid4()),
                user_id=user_id,
                avatar_url=avatar_url,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(profile)
        await db.flush()

        log.info("avatar_uploaded", user_id=user_id, url=avatar_url)
        return avatar_url

    async def delete_account(self, db: AsyncSession, redis, user_id: str) -> bool:
        anon_id = hashlib.sha256(user_id.encode()).hexdigest()[:16]

        result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
        profile = result.scalar_one_or_none()
        if profile:
            profile.full_name = f"deleted_{anon_id}"
            profile.avatar_url = None
            profile.bio = None
            profile.date_of_birth = None
            profile.updated_at = datetime.now(timezone.utc)

        await db.execute(delete(UserAddress).where(UserAddress.user_id == user_id))
        await db.execute(
            update(UserDevice)
            .where(UserDevice.user_id == user_id)
            .values(is_active=False, device_token="deleted")
        )
        await db.flush()

        log.info("account_deleted", user_id=user_id)
        return True


user_service = UserService()
