"""Bad work photos: customers report them, and admins keep, hide or remove them.

Photos go live with no check before, so this is the check. A photo stays up when first reported, as a review does,
but enough different people reporting it hides it until an admin looks: a customer's ID on show should not wait.
"""

from datetime import datetime
from typing import List, Literal, Optional

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.reporting import Reporter, get_reporter, request_origin
from app.core.storage import LocalDocumentStorage, get_storage
from app.database import get_db
from app.dependencies import Caller, require_caller
from app.models.shop import Shop, ShopWorkPhoto, WorkPhotoReport
from app.routers.kyc import require_admin
from app.schemas.review import ReportCreate, VisibilityUpdate

router = APIRouter()
log = structlog.get_logger()


class ModerationPhoto(BaseModel):
    id: str
    shop_id: str
    shop_name: str
    url: str
    caption: Optional[str] = None
    is_hidden: bool
    report_count: int
    report_reasons: List[str]
    created_at: datetime


class ModerationPhotoPage(BaseModel):
    items: List[ModerationPhoto]
    total: int


async def _reasons(db: AsyncSession, photo_ids: List[str]) -> dict:
    if not photo_ids:
        return {}
    rows = await db.execute(
        select(WorkPhotoReport.photo_id, WorkPhotoReport.reason).where(WorkPhotoReport.photo_id.in_(photo_ids))
    )
    out: dict = {}
    for photo_id, reason in rows.all():
        out.setdefault(photo_id, []).append(reason)
    return out


def _item(photo: ShopWorkPhoto, shop_name: str, reasons: List[str]) -> ModerationPhoto:
    return ModerationPhoto(
        id=photo.id,
        shop_id=photo.shop_id,
        shop_name=shop_name,
        url=f"/api/v1/shops/{photo.shop_id}/photos/{photo.id}/file",
        caption=photo.caption,
        is_hidden=photo.is_hidden,
        report_count=photo.report_count or 0,
        report_reasons=reasons,
        created_at=photo.created_at,
    )


async def _photo_and_shop(db: AsyncSession, photo_id: str):
    row = (
        await db.execute(
            select(ShopWorkPhoto, Shop).join(Shop, Shop.id == ShopWorkPhoto.shop_id).where(ShopWorkPhoto.id == photo_id)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Photo not found")
    return row


@router.post("/shops/{shop_id}/photos/{photo_id}/report", status_code=202)
async def report_photo(
    shop_id: str,
    photo_id: str,
    data: ReportCreate,
    response: Response,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db, scope="function"),
    caller: Caller = Depends(require_caller),
    reporter: Reporter = Depends(get_reporter),
):
    """Anyone signed in may flag a photo, once. Repeating it counts for nothing."""
    photo, shop = await _photo_and_shop(db, photo_id)
    if photo.shop_id != shop_id or photo.is_hidden:
        raise HTTPException(status_code=404, detail="Photo not found")
    try:
        async with db.begin_nested():
            db.add(WorkPhotoReport(photo_id=photo.id, reporter_id=caller.user_id, reason=data.reason))
            await db.flush()
    except IntegrityError:  # already reported by this person
        response.status_code = 200
        return {"status": "reported"}
    photo.report_count = (photo.report_count or 0) + 1
    if photo.report_count >= settings.PHOTO_AUTO_HIDE_REPORTS:
        photo.is_hidden = True
        background.add_task(
            reporter.notify_owner, "shop.photo_hidden", shop.owner_id, {"shop_id": shop.id, "shop_name": shop.name}
        )
    await db.flush()
    log.info("work_photo_reported", photo_id=photo.id, report_count=photo.report_count, hidden=photo.is_hidden)
    return {"status": "reported"}


@router.get("/admin/work-photos", response_model=ModerationPhotoPage, dependencies=[Depends(require_admin)])
async def moderation_queue(
    status: Literal["reported", "hidden", "all"] = "reported",
    skip: int = Query(0, ge=0),
    limit: int = Query(24, ge=1, le=100),
    db: AsyncSession = Depends(get_db, scope="function"),
):
    """Reported photos, most reported first; hidden ones; or every photo, newest first, to look through."""
    query = select(ShopWorkPhoto, Shop.name).join(Shop, Shop.id == ShopWorkPhoto.shop_id)
    count = select(func.count()).select_from(ShopWorkPhoto)
    if status == "reported":
        query = query.where(ShopWorkPhoto.report_count > 0).order_by(ShopWorkPhoto.report_count.desc())
        count = count.where(ShopWorkPhoto.report_count > 0)
    elif status == "hidden":
        query = query.where(ShopWorkPhoto.is_hidden.is_(True))
        count = count.where(ShopWorkPhoto.is_hidden.is_(True))
    rows = (
        await db.execute(query.order_by(ShopWorkPhoto.created_at.desc(), ShopWorkPhoto.id).offset(skip).limit(limit))
    ).all()
    reasons = await _reasons(db, [photo.id for photo, _ in rows])
    return ModerationPhotoPage(
        items=[_item(photo, name, reasons.get(photo.id, [])) for photo, name in rows],
        total=await db.scalar(count) or 0,
    )


@router.put("/admin/work-photos/{photo_id}", response_model=ModerationPhoto)
async def decide_photo(
    photo_id: str,
    data: VisibilityUpdate,
    request: Request,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db, scope="function"),
    caller: Caller = Depends(require_admin),
    reporter: Reporter = Depends(get_reporter),
):
    """Hide it, or keep it: keeping clears its reports, so it leaves the queue until someone new reports it."""
    photo, shop = await _photo_and_shop(db, photo_id)
    was_hidden = photo.is_hidden
    photo.is_hidden = data.hidden
    reasons = (await _reasons(db, [photo.id])).get(photo.id, [])
    if not data.hidden:
        await db.execute(delete(WorkPhotoReport).where(WorkPhotoReport.photo_id == photo.id))
        photo.report_count = 0
        reasons = []
    await db.flush()
    background.add_task(
        reporter.audit,
        caller.user_id,
        "shop.photo_hide" if data.hidden else "shop.photo_keep",
        shop.id,
        request_origin(request),
        {"photo_id": photo.id, "is_hidden": was_hidden},
        {"photo_id": photo.id, "is_hidden": data.hidden},
    )
    if data.hidden and not was_hidden:
        background.add_task(
            reporter.notify_owner, "shop.photo_hidden", shop.owner_id, {"shop_id": shop.id, "shop_name": shop.name}
        )
    return _item(photo, shop.name, reasons)


@router.delete("/admin/work-photos/{photo_id}", status_code=204)
async def remove_photo(
    photo_id: str,
    request: Request,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db, scope="function"),
    caller: Caller = Depends(require_admin),
    reporter: Reporter = Depends(get_reporter),
    storage: LocalDocumentStorage = Depends(get_storage),
):
    """Removes it for good, file included."""
    photo, shop = await _photo_and_shop(db, photo_id)
    key = photo.storage_key
    await db.execute(delete(WorkPhotoReport).where(WorkPhotoReport.photo_id == photo.id))
    await db.delete(photo)
    await db.flush()
    storage.delete(key)
    background.add_task(
        reporter.audit,
        caller.user_id,
        "shop.photo_remove",
        shop.id,
        request_origin(request),
        {"photo_id": photo_id},
        None,
    )
    background.add_task(
        reporter.notify_owner, "shop.photo_removed", shop.owner_id, {"shop_id": shop.id, "shop_name": shop.name}
    )
