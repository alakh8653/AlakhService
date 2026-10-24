"""Shop onboarding: KYC documents, payout details, submitting for review, and the admins' review queue.

Everything here is for the shop's owner and admins only. Documents are either https links the owner
gives or files uploaded here (PDF, JPEG, PNG or WebP, at most DOCUMENT_MAX_BYTES), which are only ever
served back through the API.
"""

import re
import uuid
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import ShopNotFoundError
from app.core.reporting import Reporter, get_reporter, request_origin
from app.core.storage import LocalDocumentStorage, StorageDisabled, get_storage, sniff_content_type
from app.database import get_db
from app.dependencies import Caller, ensure_owner, require_caller
from app.models.shop import PENDING_REVIEW, VERIFICATION_STATUSES, Shop
from app.schemas.shop import (
    AdminShopList,
    DocumentType,
    PayoutDetailsIn,
    PayoutDetailsOut,
    ReviewDecision,
    ShopDocumentCreate,
    ShopDocumentResponse,
    ShopResponse,
    ShopReviewItem,
)
from app.services.kyc_service import ReviewStateError, kyc_service
from app.services.shop_service import is_public, shop_service

router = APIRouter()


def require_admin(caller: Caller = Depends(require_caller)) -> Caller:
    if not caller.is_admin:
        raise HTTPException(status_code=403, detail="Admins only")
    return caller


async def managed_shop(shop_id: str, db: AsyncSession, caller: Caller) -> Shop:
    """The shop, when the caller is its owner or an admin (404 when it does not exist)."""
    try:
        shop = await shop_service.get_shop(db, shop_id)
    except ShopNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    ensure_owner(shop.owner_id, caller)
    return shop


async def _ensure_room(db: AsyncSession, shop_id: str) -> None:
    if await kyc_service.count_documents(db, shop_id) >= settings.MAX_DOCUMENTS_PER_SHOP:
        raise HTTPException(
            status_code=409,
            detail=f"A shop can keep at most {settings.MAX_DOCUMENTS_PER_SHOP} documents; delete one first",
        )


def _safe_file_name(name: Optional[str]) -> Optional[str]:
    """A display name only (never a path): letters, digits, spaces, dots, dashes and underscores."""
    cleaned = re.sub(r"[^A-Za-z0-9 ._-]", "_", (name or "").strip().split("/")[-1].split("\\")[-1])[:255]
    return cleaned or None


# Documents


@router.get("/shops/{shop_id}/documents", response_model=List[ShopDocumentResponse])
async def list_documents(shop_id: str, db: AsyncSession = Depends(get_db), caller: Caller = Depends(require_caller)):
    await managed_shop(shop_id, db, caller)
    return await kyc_service.list_documents(db, shop_id)


@router.post("/shops/{shop_id}/documents", response_model=ShopDocumentResponse, status_code=201)
async def add_document_link(
    shop_id: str,
    data: ShopDocumentCreate,
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(require_caller),
):
    """Records a document kept elsewhere, by its https link."""
    await managed_shop(shop_id, db, caller)
    await _ensure_room(db, shop_id)
    return await kyc_service.add_document(
        db, shop_id, data.type, data.url, caller.user_id, file_name=_safe_file_name(data.file_name)
    )


@router.post("/shops/{shop_id}/documents/upload", response_model=ShopDocumentResponse, status_code=201)
async def upload_document(
    shop_id: str,
    request: Request,
    type: DocumentType = Query(..., description="PAN, GST, AADHAAR, UDYAM, BANK_PROOF or SHOP_PHOTO"),
    file_name: Optional[str] = Query(None, max_length=255),
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(require_caller),
    storage: LocalDocumentStorage = Depends(get_storage),
):
    """Uploads a document file: the raw file is the request body and Content-Type says what it is."""
    await managed_shop(shop_id, db, caller)
    if not storage.enabled:
        raise HTTPException(status_code=501, detail="File uploads are off; add the document as an https link")
    limit = settings.DOCUMENT_MAX_BYTES
    too_large = HTTPException(status_code=413, detail=f"File too large (max {limit // (1024 * 1024)} MB)")
    if int(request.headers.get("content-length") or 0) > limit:
        raise too_large
    await _ensure_room(db, shop_id)
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > limit:
            raise too_large
    if not body:
        raise HTTPException(status_code=422, detail="The file is empty")
    content_type = sniff_content_type(bytes(body), request.headers.get("content-type"))
    if content_type is None:
        raise HTTPException(status_code=415, detail="Upload a PDF, JPEG, PNG or WebP file")
    try:
        key = storage.save(shop_id, bytes(body), content_type)
    except (StorageDisabled, OSError) as e:
        raise HTTPException(status_code=503, detail="Could not store the file; please try again") from e
    document_id = str(uuid.uuid4())
    return await kyc_service.add_document(
        db,
        shop_id,
        type,
        f"/api/v1/shops/{shop_id}/documents/{document_id}/file",
        caller.user_id,
        document_id=document_id,
        storage_key=key,
        file_name=_safe_file_name(file_name),
        content_type=content_type,
        size_bytes=len(body),
    )


@router.get("/shops/{shop_id}/documents/{document_id}/file")
async def download_document(
    shop_id: str,
    document_id: str,
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(require_caller),
    storage: LocalDocumentStorage = Depends(get_storage),
):
    await managed_shop(shop_id, db, caller)
    doc = await kyc_service.get_document(db, shop_id, document_id)
    if doc is None or not doc.storage_key:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        path = storage.path_of(doc.storage_key)
    except (StorageDisabled, ValueError) as e:
        raise HTTPException(status_code=404, detail="Document not found") from e
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Document not found")
    return FileResponse(
        path,
        media_type=doc.content_type or "application/octet-stream",
        filename=doc.file_name or path.name,
        content_disposition_type="inline",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'",
        },
    )


@router.delete("/shops/{shop_id}/documents/{document_id}", status_code=204)
async def delete_document(
    shop_id: str,
    document_id: str,
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(require_caller),
    storage: LocalDocumentStorage = Depends(get_storage),
):
    await managed_shop(shop_id, db, caller)
    doc = await kyc_service.get_document(db, shop_id, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    # A document an admin has checked stays on record; support removes it if it must go.
    if doc.is_verified and not caller.is_admin:
        raise HTTPException(status_code=409, detail="A verified document cannot be deleted")
    key = doc.storage_key
    await kyc_service.delete_document(db, doc)
    if key:
        storage.delete(key)
    return Response(status_code=204)


# Payout details


@router.get("/shops/{shop_id}/payout-details", response_model=PayoutDetailsOut)
async def get_payout_details(
    shop_id: str, db: AsyncSession = Depends(get_db), caller: Caller = Depends(require_caller)
):
    await managed_shop(shop_id, db, caller)
    details = await kyc_service.get_payout_details(db, shop_id)
    if details is None:
        raise HTTPException(status_code=404, detail="No payout details yet")
    return PayoutDetailsOut.masked(details)


@router.put("/shops/{shop_id}/payout-details", response_model=PayoutDetailsOut)
async def set_payout_details(
    shop_id: str,
    data: PayoutDetailsIn,
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(require_caller),
):
    await managed_shop(shop_id, db, caller)
    return PayoutDetailsOut.masked(await kyc_service.set_payout_details(db, shop_id, data, caller.user_id))


# Review


@router.post("/shops/{shop_id}/submit-for-review", response_model=ShopResponse)
async def submit_for_review(shop_id: str, db: AsyncSession = Depends(get_db), caller: Caller = Depends(require_caller)):
    """The owner asks for their shop to be checked (again, after a rejection)."""
    shop = await managed_shop(shop_id, db, caller)
    try:
        return await kyc_service.submit(db, shop)
    except ReviewStateError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


async def _review_item(db: AsyncSession, shop: Shop) -> ShopReviewItem:
    documents = await kyc_service.list_documents(db, shop.id)
    return ShopReviewItem.model_validate(
        {
            **ShopResponse.model_validate(shop).model_dump(exclude={"average_rating", "review_count"}),
            "documents": [ShopDocumentResponse.model_validate(d) for d in documents],
            "has_payout_details": await kyc_service.get_payout_details(db, shop.id) is not None,
        }
    )


@router.get("/admin/shops", response_model=AdminShopList, dependencies=[Depends(require_admin)])
async def admin_list_shops(
    status: Optional[str] = Query(None, pattern="^(" + "|".join(VERIFICATION_STATUSES) + ")$"),
    q: Optional[str] = Query(None, max_length=100),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Every shop, whatever its status, for the admin dashboard."""
    items, total = await kyc_service.admin_list(db, status=status, q=q, skip=skip, limit=limit)
    return {"items": items, "total": total}


@router.get("/admin/shops/review-queue", response_model=List[ShopReviewItem], dependencies=[Depends(require_admin)])
async def review_queue(
    skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), db: AsyncSession = Depends(get_db)
):
    """Shops submitted for review and still waiting, oldest submission first, with their documents."""
    shops, _ = await kyc_service.admin_list(db, status=PENDING_REVIEW, submitted_only=True, skip=skip, limit=limit)
    return [await _review_item(db, s) for s in shops]


@router.get("/admin/shops/{shop_id}", response_model=ShopReviewItem, dependencies=[Depends(require_admin)])
async def admin_get_shop(shop_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await _review_item(db, await shop_service.get_shop(db, shop_id))
    except ShopNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


async def _admin_shop(db: AsyncSession, shop_id: str) -> Shop:
    try:
        return await shop_service.get_shop(db, shop_id)
    except ShopNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/admin/shops/{shop_id}/approve", response_model=ShopResponse)
async def approve_shop(
    shop_id: str,
    request: Request,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(require_admin),
    reporter: Reporter = Depends(get_reporter),
):
    shop = await _admin_shop(db, shop_id)
    old = shop.verification_status
    try:
        shop = await kyc_service.approve(db, shop, caller.user_id)
    except ReviewStateError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    background.add_task(
        reporter.audit,
        caller.user_id,
        "shop.approve",
        shop.id,
        request_origin(request),
        {"verification_status": old},
        {"verification_status": shop.verification_status},
    )
    background.add_task(
        reporter.notify_owner, "shop.approved", shop.owner_id, {"shop_id": shop.id, "shop_name": shop.name}
    )
    background.add_task(reporter.sync_listing, shop.id, is_public(shop))
    return shop


@router.post("/admin/shops/{shop_id}/reject", response_model=ShopResponse)
async def reject_shop(
    shop_id: str,
    decision: ReviewDecision,
    request: Request,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(require_admin),
    reporter: Reporter = Depends(get_reporter),
):
    shop = await _admin_shop(db, shop_id)
    old = shop.verification_status
    shop = await kyc_service.reject(db, shop, caller.user_id, decision.reason)
    background.add_task(
        reporter.audit,
        caller.user_id,
        "shop.reject",
        shop.id,
        request_origin(request),
        {"verification_status": old},
        {"verification_status": shop.verification_status, "rejection_reason": decision.reason},
    )
    background.add_task(
        reporter.notify_owner,
        "shop.rejected",
        shop.owner_id,
        {"shop_id": shop.id, "shop_name": shop.name, "reason": decision.reason},
    )
    background.add_task(reporter.sync_listing, shop.id, False)
    return shop
