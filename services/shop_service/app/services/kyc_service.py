"""Shop onboarding: KYC documents, payout details, submitting for review and the admin's decision."""

from datetime import datetime, timezone
from typing import List, Optional, Tuple

import structlog
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shop import APPROVED, PENDING_REVIEW, REJECTED, Shop, ShopDocument, ShopPayoutDetails
from app.schemas.shop import PayoutDetailsIn

log = structlog.get_logger()


class ReviewStateError(Exception):
    """The shop is not in a state that allows this step."""


def now() -> datetime:
    return datetime.now(timezone.utc)


def missing_for_review(shop: Shop, documents: List[ShopDocument]) -> List[str]:
    """What an owner still has to provide before an admin can review the shop."""
    missing = []
    if not shop.legal_name:
        missing.append("legal name")
    if not any(d.type == "PAN" for d in documents):
        missing.append("PAN document")
    if shop.gstin and not any(d.type == "GST" for d in documents):
        missing.append("GST certificate (you gave a GSTIN)")
    return missing


class KycService:
    # Documents

    async def list_documents(self, db: AsyncSession, shop_id: str) -> List[ShopDocument]:
        result = await db.execute(
            select(ShopDocument).where(ShopDocument.shop_id == shop_id).order_by(ShopDocument.created_at)
        )
        return list(result.scalars().all())

    async def count_documents(self, db: AsyncSession, shop_id: str) -> int:
        result = await db.execute(select(func.count()).select_from(ShopDocument).where(ShopDocument.shop_id == shop_id))
        return int(result.scalar_one())

    async def get_document(self, db: AsyncSession, shop_id: str, document_id: str) -> Optional[ShopDocument]:
        result = await db.execute(
            select(ShopDocument).where(ShopDocument.id == document_id, ShopDocument.shop_id == shop_id)
        )
        return result.scalar_one_or_none()

    async def add_document(
        self,
        db: AsyncSession,
        shop_id: str,
        doc_type: str,
        url: str,
        uploaded_by: str,
        *,
        document_id: Optional[str] = None,
        storage_key: Optional[str] = None,
        file_name: Optional[str] = None,
        content_type: Optional[str] = None,
        size_bytes: Optional[int] = None,
    ) -> ShopDocument:
        kwargs = {"id": document_id} if document_id else {}
        doc = ShopDocument(
            **kwargs,
            shop_id=shop_id,
            type=doc_type,
            url=url,
            is_verified=False,
            storage_key=storage_key,
            file_name=file_name,
            content_type=content_type,
            size_bytes=size_bytes,
            uploaded_by=uploaded_by,
            created_at=now(),
        )
        db.add(doc)
        await db.flush()
        log.info("shop_document_added", shop_id=shop_id, document_id=doc.id, type=doc_type)
        return doc

    async def delete_document(self, db: AsyncSession, doc: ShopDocument) -> None:
        await db.delete(doc)
        await db.flush()

    # Payout details

    async def get_payout_details(self, db: AsyncSession, shop_id: str) -> Optional[ShopPayoutDetails]:
        return await db.get(ShopPayoutDetails, shop_id)

    async def set_payout_details(
        self, db: AsyncSession, shop_id: str, data: PayoutDetailsIn, updated_by: str
    ) -> ShopPayoutDetails:
        details = await db.get(ShopPayoutDetails, shop_id)
        if details is None:
            details = ShopPayoutDetails(shop_id=shop_id)
            db.add(details)
        details.method = data.method
        details.account_name = data.account_name
        details.account_number = data.account_number
        details.ifsc = data.ifsc
        details.upi_id = data.upi_id
        details.updated_at = now()
        details.updated_by = updated_by
        await db.flush()
        log.info("shop_payout_details_set", shop_id=shop_id, method=data.method)
        return details

    # Review

    async def submit(self, db: AsyncSession, shop: Shop) -> Shop:
        if shop.verification_status == APPROVED:
            raise ReviewStateError("This shop is already approved")
        missing = missing_for_review(shop, await self.list_documents(db, shop.id))
        if missing:
            raise ReviewStateError("Before submitting, add: " + ", ".join(missing))
        shop.verification_status = PENDING_REVIEW
        shop.is_verified = False
        shop.rejection_reason = None
        shop.submitted_at = now()
        await db.flush()
        log.info("shop_submitted_for_review", shop_id=shop.id)
        return shop

    async def approve(self, db: AsyncSession, shop: Shop, admin_id: str) -> Shop:
        if shop.verification_status == APPROVED:
            raise ReviewStateError("This shop is already approved")
        shop.verification_status = APPROVED
        shop.is_verified = True
        shop.rejection_reason = None
        shop.reviewed_at = now()
        shop.reviewed_by = admin_id
        for doc in await self.list_documents(db, shop.id):
            doc.is_verified = True
        await db.flush()
        log.info("shop_approved", shop_id=shop.id, admin_id=admin_id)
        return shop

    async def reject(self, db: AsyncSession, shop: Shop, admin_id: str, reason: str) -> Shop:
        # An approved shop can be rejected too (e.g. a forged document found later): it leaves the listings.
        shop.verification_status = REJECTED
        shop.is_verified = False
        shop.rejection_reason = reason
        shop.reviewed_at = now()
        shop.reviewed_by = admin_id
        await db.flush()
        log.info("shop_rejected", shop_id=shop.id, admin_id=admin_id)
        return shop

    async def admin_list(
        self,
        db: AsyncSession,
        status: Optional[str] = None,
        q: Optional[str] = None,
        submitted_only: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Shop], int]:
        conditions = []
        if status:
            conditions.append(Shop.verification_status == status)
        if submitted_only:
            conditions.append(Shop.submitted_at.is_not(None))
        if q:
            like = f"%{q}%"
            conditions.append(
                or_(Shop.name.ilike(like), Shop.legal_name.ilike(like), Shop.gstin.ilike(like), Shop.city.ilike(like))
            )
        total = (await db.execute(select(func.count()).select_from(Shop).where(*conditions))).scalar_one()
        # The review queue is first come, first served; other lists show the newest shops first.
        order = (Shop.submitted_at, Shop.id) if submitted_only else (Shop.created_at.desc(), Shop.id)
        result = await db.execute(select(Shop).where(*conditions).order_by(*order).offset(skip).limit(limit))
        return list(result.scalars().all()), int(total)


kyc_service = KycService()
