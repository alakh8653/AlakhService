import uuid
from datetime import datetime, timezone
from typing import List, Optional

import structlog
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import RatingExistsError, ShopNotFoundError
from app.models.shop import APPROVED, PENDING_REVIEW, Shop, ShopRating
from app.schemas.shop import ShopCreate, ShopUpdate
from app.services.review_service import review_service

log = structlog.get_logger()

# What customers may find: approved by an admin and not closed by its owner.
PUBLIC = (Shop.is_active == True, Shop.verification_status == APPROVED)


def is_public(shop: Shop) -> bool:
    return bool(shop.is_active) and shop.verification_status == APPROVED


class ShopService:
    async def create_shop(self, db: AsyncSession, data: ShopCreate) -> Shop:
        shop = Shop(
            id=str(uuid.uuid4()),
            owner_id=data.owner_id,
            name=data.name,
            category=data.category,
            description=data.description,
            city=data.city,
            address=data.address,
            phone=data.phone,
            email=data.email,
            latitude=data.latitude,
            longitude=data.longitude,
            rating_avg=0.0,
            rating_count=0,
            is_active=True,
            # Hidden from customers until an admin has checked its documents.
            is_verified=False,
            verification_status=PENDING_REVIEW,
            legal_name=data.legal_name,
            legal_address=data.legal_address,
            gstin=data.gstin,
        )
        db.add(shop)
        await db.flush()
        log.info("shop_created", shop_id=shop.id, name=shop.name)
        return shop

    async def get_shop(self, db: AsyncSession, shop_id: str) -> Shop:
        result = await db.execute(select(Shop).where(Shop.id == shop_id))
        shop = result.scalar_one_or_none()
        if not shop:
            raise ShopNotFoundError()
        return shop

    async def list_shops(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 20,
        owner_id: Optional[str] = None,
        include_hidden: bool = False,
    ) -> List[Shop]:
        """Approved, active shops; include_hidden (the owner's own list) adds the rest of theirs."""
        query = select(Shop)
        if owner_id:
            query = query.where(Shop.owner_id == owner_id)
        if not (owner_id and include_hidden):
            query = query.where(*PUBLIC)
        result = await db.execute(query.order_by(Shop.created_at, Shop.id).offset(skip).limit(limit))
        return list(result.scalars().all())

    async def owner_has_shop(self, db: AsyncSession, owner_id: str) -> bool:
        result = await db.execute(select(Shop.id).where(Shop.owner_id == owner_id).limit(1))
        return result.first() is not None

    async def search_shops(
        self,
        db: AsyncSession,
        q: Optional[str] = None,
        city: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[Shop]:
        stmt = select(Shop).where(*PUBLIC)
        if city:
            stmt = stmt.where(Shop.city == city)
        if category:
            stmt = stmt.where(Shop.category == category)
        if q:
            stmt = stmt.where(or_(Shop.name.ilike(f"%{q}%"), Shop.description.ilike(f"%{q}%")))
        # Same stable order as list_shops, so the limit cuts the same matches every time.
        result = await db.execute(stmt.order_by(Shop.created_at, Shop.id).limit(limit))
        return list(result.scalars().all())

    async def update_shop(self, db: AsyncSession, shop_id: str, data: ShopUpdate) -> Shop:
        shop = await self.get_shop(db, shop_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(shop, field, value)
        await db.flush()
        log.info("shop_updated", shop_id=shop_id)
        return shop

    async def delete_shop(self, db: AsyncSession, shop_id: str) -> None:
        shop = await self.get_shop(db, shop_id)
        shop.is_active = False
        await db.flush()
        log.info("shop_deleted", shop_id=shop_id)

    async def update_rating(self, db: AsyncSession, shop_id: str, new_rating: float) -> Shop:
        shop = await self.get_shop(db, shop_id)
        total = shop.rating_avg * shop.rating_count + new_rating
        shop.rating_count += 1
        shop.rating_avg = total / shop.rating_count
        await db.flush()
        log.info("shop_rating_updated", shop_id=shop_id, new_avg=shop.rating_avg)
        return shop

    async def add_rating(
        self,
        db: AsyncSession,
        shop_id: str,
        booking_id: str,
        customer_id: str,
        rating: float,
        comment=None,
        service_id: Optional[str] = None,
        reviewer_name: Optional[str] = None,
    ) -> Shop:
        """Record a booking's rating (and optional written review) once and refresh the shop's average."""
        await self.get_shop(db, shop_id)
        existing = await db.execute(select(ShopRating).where(ShopRating.booking_id == booking_id))
        if existing.scalar_one_or_none() is not None:
            raise RatingExistsError()
        db.add(
            ShopRating(
                shop_id=shop_id,
                booking_id=booking_id,
                customer_id=customer_id,
                service_id=service_id,
                reviewer_name=reviewer_name,
                rating=rating,
                comment=comment,
                created_at=datetime.now(timezone.utc),
            )
        )
        try:
            await db.flush()
        except IntegrityError:  # the same booking rated concurrently
            await db.rollback()
            raise RatingExistsError() from None
        shop = await review_service.refresh_shop_rating(db, shop_id)
        log.info("shop_rated", shop_id=shop_id, new_avg=shop.rating_avg)
        return shop


shop_service = ShopService()
