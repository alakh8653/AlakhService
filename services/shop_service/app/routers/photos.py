"""Photos of a business's work, which customers see before they book.

Unlike KYC documents these are public, so each is re-saved on the way in: see app/core/photos.py.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.contact_filter import mask_contact
from app.core.exceptions import ShopNotFoundError
from app.core.photos import NotAPhoto, clean_photo
from app.core.storage import LocalDocumentStorage, StorageDisabled, get_storage
from app.database import get_db
from app.dependencies import Caller, ensure_owner, optional_caller, require_caller
from app.models.shop import ShopWorkPhoto, WorkPhotoReport
from app.services.shop_service import is_public, shop_service

router = APIRouter()


class WorkPhotoResponse(BaseModel):
    id: str
    url: str
    caption: Optional[str] = None
    # Only the owner and admins are ever sent a hidden photo.
    is_hidden: bool = False


def _response(photo: ShopWorkPhoto, may_edit: bool) -> WorkPhotoResponse:
    caption = photo.caption if may_edit or not photo.caption else mask_contact(photo.caption).text
    return WorkPhotoResponse(
        id=photo.id,
        url=f"/api/v1/shops/{photo.shop_id}/photos/{photo.id}/file",
        caption=caption,
        is_hidden=bool(photo.is_hidden),
    )


async def _shop(db: AsyncSession, shop_id: str):
    try:
        return await shop_service.get_shop(db, shop_id)
    except ShopNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


async def _photos(db: AsyncSession, shop_id: str) -> List[ShopWorkPhoto]:
    result = await db.execute(
        select(ShopWorkPhoto).where(ShopWorkPhoto.shop_id == shop_id).order_by(ShopWorkPhoto.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/shops/{shop_id}/photos", response_model=List[WorkPhotoResponse])
async def list_photos(
    shop_id: str,
    db: AsyncSession = Depends(get_db, scope="function"),
    caller: Optional[Caller] = Depends(optional_caller),
):
    """Public once the shop is; until then only its owner and admins see them."""
    shop = await _shop(db, shop_id)
    may_edit = caller is not None and (caller.is_admin or caller.user_id == shop.owner_id)
    if not is_public(shop) and not may_edit:
        raise HTTPException(status_code=404, detail="Shop not found")
    return [_response(p, may_edit) for p in await _photos(db, shop_id) if may_edit or not p.is_hidden]


@router.post("/shops/{shop_id}/photos", response_model=WorkPhotoResponse, status_code=201)
async def add_photo(
    shop_id: str,
    request: Request,
    caption: Optional[str] = Query(None, max_length=120),
    db: AsyncSession = Depends(get_db, scope="function"),
    caller: Caller = Depends(require_caller),
    storage: LocalDocumentStorage = Depends(get_storage),
):
    """Adds a photo: the raw image is the request body. Its location and other details are removed."""
    shop = await _shop(db, shop_id)
    ensure_owner(shop.owner_id, caller)
    if not storage.enabled:
        raise HTTPException(status_code=501, detail="Photo uploads are off")
    count = await db.scalar(select(func.count()).select_from(ShopWorkPhoto).where(ShopWorkPhoto.shop_id == shop_id))
    if count >= settings.MAX_WORK_PHOTOS:
        raise HTTPException(
            status_code=409, detail=f"You can keep {settings.MAX_WORK_PHOTOS} photos; remove one to add another"
        )
    limit = settings.DOCUMENT_MAX_BYTES
    too_large = HTTPException(status_code=413, detail=f"Photo too large (max {limit // (1024 * 1024)} MB)")
    if int(request.headers.get("content-length") or 0) > limit:
        raise too_large
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > limit:
            raise too_large
    try:
        cleaned = clean_photo(bytes(body))
    except NotAPhoto as e:
        raise HTTPException(status_code=422, detail="That file is not a photo we can use") from e
    key = storage.save(shop_id, cleaned, "image/jpeg")
    photo = ShopWorkPhoto(
        id=str(uuid.uuid4()),
        shop_id=shop_id,
        storage_key=key,
        caption=(caption or "").strip() or None,
        created_at=datetime.now(timezone.utc),
    )
    db.add(photo)
    await db.flush()
    return _response(photo, True)


@router.get("/shops/{shop_id}/photos/{photo_id}/file")
async def photo_file(
    shop_id: str,
    photo_id: str,
    db: AsyncSession = Depends(get_db, scope="function"),
    storage: LocalDocumentStorage = Depends(get_storage),
    caller: Optional[Caller] = Depends(optional_caller),
):
    """The image. Public to read, as profile photos are: images load without a token and ids are random.

    A hidden one only for an admin judging it or its owner. Kept in caches briefly, so that it goes soon after.
    """
    photo = await db.get(ShopWorkPhoto, photo_id)
    if photo is None or photo.shop_id != shop_id:
        raise HTTPException(status_code=404, detail="Not found")
    if photo.is_hidden:
        shop = await _shop(db, shop_id)
        if caller is None or not (caller.is_admin or caller.user_id == shop.owner_id):
            raise HTTPException(status_code=404, detail="Not found")
    try:
        path = storage.path_of(photo.storage_key)
    except (StorageDisabled, ValueError):
        raise HTTPException(status_code=404, detail="Not found") from None
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(
        path,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "public, max-age=300",
            "X-Content-Type-Options": "nosniff",
            "Cross-Origin-Resource-Policy": "cross-origin",
        },
    )


@router.delete("/shops/{shop_id}/photos/{photo_id}", status_code=204)
async def delete_photo(
    shop_id: str,
    photo_id: str,
    db: AsyncSession = Depends(get_db, scope="function"),
    caller: Caller = Depends(require_caller),
    storage: LocalDocumentStorage = Depends(get_storage),
):
    """By its owner, or an admin taking down one that should not be shown."""
    shop = await _shop(db, shop_id)
    ensure_owner(shop.owner_id, caller)
    photo = await db.get(ShopWorkPhoto, photo_id)
    if photo is None or photo.shop_id != shop_id:
        raise HTTPException(status_code=404, detail="Not found")
    key = photo.storage_key
    await db.execute(delete(WorkPhotoReport).where(WorkPhotoReport.photo_id == photo.id))
    await db.delete(photo)
    await db.flush()
    storage.delete(key)
