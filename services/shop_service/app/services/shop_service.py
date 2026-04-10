import uuid
from datetime import datetime, timezone
from typing import List, Optional
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.models.shop import Shop, ShopDocument, ShopHours
from app.schemas.shop import ShopCreate, ShopUpdate
from app.core.exceptions import ShopNotFoundError

log = structlog.get_logger()


class ShopService:

    async def create_shop(self, db: AsyncSession, data: ShopCreate) -> Shop:
        shop = Shop(
            id=str(uuid.uuid4()),
            owner_id=data.owner_id,
            name=data.name,
            category=data.category,
            description=data.description,
            city=data.city,
            latitude=data.latitude,
            longitude=data.longitude,
            rating_avg=0.0,
            rating_count=0,
            is_active=True,
            is_verified=False,
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

    async def list_shops(self, db: AsyncSession, skip: int = 0, limit: int = 20) -> List[Shop]:
        result = await db.execute(select(Shop).where(Shop.is_active == True).offset(skip).limit(limit))
        return list(result.scalars().all())

    async def search_shops(self, db: AsyncSession, q: Optional[str] = None, city: Optional[str] = None, category: Optional[str] = None) -> List[Shop]:
        stmt = select(Shop).where(Shop.is_active == True)
        if city:
            stmt = stmt.where(Shop.city == city)
        if category:
            stmt = stmt.where(Shop.category == category)
        if q:
            stmt = stmt.where(or_(Shop.name.ilike(f"%{q}%"), Shop.description.ilike(f"%{q}%")))
        result = await db.execute(stmt)
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


shop_service = ShopService()
