import json
import structlog
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload

from app.models.catalog import ServiceCategory, ServiceItem, PricingTier, ServiceMedia, ServiceVariant
from app.schemas.catalog import (
    ServiceCategoryCreate, ServiceCategoryUpdate,
    ServiceItemCreate, ServiceItemUpdate,
    PricingTierCreate, ServiceMediaCreate, ServiceVariantCreate,
    ServiceItemListResponse,
)
from app.core.exceptions import CategoryNotFoundError, ServiceNotFoundError, SlugConflictError
from app.config import settings

log = structlog.get_logger()
CACHE_KEY_TREE = "catalog:tree"
CACHE_KEY_FEATURED = "catalog:featured"
CACHE_KEY_POPULAR = "catalog:popular:{limit}"

class CatalogService:
    async def create_category(self, db: AsyncSession, data: ServiceCategoryCreate) -> ServiceCategory:
        existing = await db.execute(select(ServiceCategory).where(ServiceCategory.slug == data.slug))
        if existing.scalar_one_or_none():
            raise SlugConflictError(f"Slug '{data.slug}' already exists")
        cat = ServiceCategory(**data.model_dump())
        db.add(cat)
        await db.flush()
        return cat

    async def get_category(self, db: AsyncSession, category_id: str) -> ServiceCategory:
        result = await db.execute(select(ServiceCategory).options(selectinload(ServiceCategory.children)).where(ServiceCategory.id == category_id))
        cat = result.scalar_one_or_none()
        if not cat:
            raise CategoryNotFoundError()
        return cat

    async def update_category(self, db: AsyncSession, category_id: str, data: ServiceCategoryUpdate) -> ServiceCategory:
        cat = await self.get_category(db, category_id)
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(cat, field, value)
        await db.flush()
        return cat

    async def delete_category(self, db: AsyncSession, category_id: str) -> bool:
        cat = await self.get_category(db, category_id)
        cat.is_active = False
        await db.flush()
        return True

    async def list_categories(self, db: AsyncSession, parent_id: Optional[str] = None) -> List[ServiceCategory]:
        q = select(ServiceCategory).options(selectinload(ServiceCategory.children)).where(ServiceCategory.is_active == True)
        if parent_id is not None:
            q = q.where(ServiceCategory.parent_id == parent_id)
        else:
            q = q.where(ServiceCategory.parent_id.is_(None))
        result = await db.execute(q.order_by(ServiceCategory.order))
        return result.scalars().all()

    async def get_service_tree(self, db: AsyncSession, redis=None) -> List[dict]:
        if redis:
            cached = await redis.get(CACHE_KEY_TREE)
            if cached:
                return json.loads(cached)
        root_cats = await self.list_categories(db, parent_id=None)
        tree = [await self._build_tree_node(db, cat) for cat in root_cats]
        if redis:
            await redis.setex(CACHE_KEY_TREE, settings.CACHE_TTL_SECONDS, json.dumps(tree))
        return tree

    async def _build_tree_node(self, db: AsyncSession, cat: ServiceCategory) -> dict:
        result = await db.execute(select(ServiceCategory).where(ServiceCategory.parent_id == cat.id, ServiceCategory.is_active == True).order_by(ServiceCategory.order))
        children = result.scalars().all()
        return {"id": cat.id, "name": cat.name, "slug": cat.slug, "icon_url": cat.icon_url, "order": cat.order, "children": [await self._build_tree_node(db, c) for c in children]}

    async def create_service(self, db: AsyncSession, data: ServiceItemCreate) -> ServiceItem:
        existing = await db.execute(select(ServiceItem).where(ServiceItem.slug == data.slug))
        if existing.scalar_one_or_none():
            raise SlugConflictError(f"Slug '{data.slug}' already exists")
        dump = data.model_dump()
        metadata = dump.pop("metadata", None)
        svc = ServiceItem(**dump, metadata_json=json.dumps(metadata) if metadata else None)
        db.add(svc)
        await db.flush()
        return svc

    async def get_service(self, db: AsyncSession, service_id: str) -> ServiceItem:
        result = await db.execute(select(ServiceItem).options(selectinload(ServiceItem.pricing_tiers), selectinload(ServiceItem.media), selectinload(ServiceItem.variants)).where(ServiceItem.id == service_id))
        svc = result.scalar_one_or_none()
        if not svc:
            raise ServiceNotFoundError()
        return svc

    async def get_service_by_slug(self, db: AsyncSession, slug: str) -> ServiceItem:
        result = await db.execute(select(ServiceItem).options(selectinload(ServiceItem.pricing_tiers), selectinload(ServiceItem.media), selectinload(ServiceItem.variants)).where(ServiceItem.slug == slug, ServiceItem.is_active == True))
        svc = result.scalar_one_or_none()
        if not svc:
            raise ServiceNotFoundError()
        return svc

    async def update_service(self, db: AsyncSession, service_id: str, data: ServiceItemUpdate) -> ServiceItem:
        svc = await self.get_service(db, service_id)
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(svc, field, value)
        await db.flush()
        return svc

    async def delete_service(self, db: AsyncSession, service_id: str) -> bool:
        svc = await self.get_service(db, service_id)
        svc.is_active = False
        await db.flush()
        return True

    async def list_services(self, db: AsyncSession, category_id: Optional[str] = None, page: int = 1, per_page: int = 20) -> ServiceItemListResponse:
        q = select(ServiceItem).options(selectinload(ServiceItem.pricing_tiers), selectinload(ServiceItem.media), selectinload(ServiceItem.variants)).where(ServiceItem.is_active == True)
        if category_id:
            q = q.where(ServiceItem.category_id == category_id)
        count_q = select(func.count()).select_from(ServiceItem).where(ServiceItem.is_active == True)
        if category_id:
            count_q = count_q.where(ServiceItem.category_id == category_id)
        total = (await db.execute(count_q)).scalar_one()
        q = q.offset((page - 1) * per_page).limit(per_page)
        items = (await db.execute(q)).scalars().all()
        return ServiceItemListResponse(items=items, total=total, page=page, per_page=per_page)

    async def search_catalog(self, db: AsyncSession, query: Optional[str] = None, category_id: Optional[str] = None, min_price_cents: Optional[int] = None, max_price_cents: Optional[int] = None, page: int = 1, per_page: int = 20) -> ServiceItemListResponse:
        q = select(ServiceItem).options(selectinload(ServiceItem.pricing_tiers), selectinload(ServiceItem.media), selectinload(ServiceItem.variants)).where(ServiceItem.is_active == True)
        if query:
            like = f"%{query}%"
            q = q.where(or_(ServiceItem.name.ilike(like), ServiceItem.description.ilike(like)))
        if category_id:
            q = q.where(ServiceItem.category_id == category_id)
        if min_price_cents is not None:
            q = q.where(ServiceItem.base_price_cents >= min_price_cents)
        if max_price_cents is not None:
            q = q.where(ServiceItem.base_price_cents <= max_price_cents)
        count_q = select(func.count()).select_from(q.subquery())
        total = (await db.execute(count_q)).scalar_one()
        q = q.offset((page - 1) * per_page).limit(per_page)
        items = (await db.execute(q)).scalars().all()
        return ServiceItemListResponse(items=items, total=total, page=page, per_page=per_page)

    async def get_popular_services(self, db: AsyncSession, redis=None, limit: int = 10) -> List[ServiceItem]:
        cache_key = CACHE_KEY_POPULAR.format(limit=limit)
        if redis:
            cached = await redis.get(cache_key)
            if cached:
                ids = json.loads(cached)
                result = await db.execute(select(ServiceItem).options(selectinload(ServiceItem.pricing_tiers), selectinload(ServiceItem.media), selectinload(ServiceItem.variants)).where(ServiceItem.id.in_(ids)))
                return result.scalars().all()
        result = await db.execute(select(ServiceItem).options(selectinload(ServiceItem.pricing_tiers), selectinload(ServiceItem.media), selectinload(ServiceItem.variants)).where(ServiceItem.is_active == True).order_by(ServiceItem.booking_count.desc()).limit(limit))
        items = result.scalars().all()
        if redis:
            await redis.setex(cache_key, settings.CACHE_TTL_SECONDS, json.dumps([i.id for i in items]))
        return items

    async def get_featured_services(self, db: AsyncSession, redis=None) -> List[ServiceItem]:
        if redis:
            cached = await redis.get(CACHE_KEY_FEATURED)
            if cached:
                ids = json.loads(cached)
                result = await db.execute(select(ServiceItem).options(selectinload(ServiceItem.pricing_tiers), selectinload(ServiceItem.media), selectinload(ServiceItem.variants)).where(ServiceItem.id.in_(ids)))
                return result.scalars().all()
        result = await db.execute(select(ServiceItem).options(selectinload(ServiceItem.pricing_tiers), selectinload(ServiceItem.media), selectinload(ServiceItem.variants)).where(ServiceItem.is_active == True, ServiceItem.is_featured == True))
        items = result.scalars().all()
        if redis:
            await redis.setex(CACHE_KEY_FEATURED, settings.CACHE_TTL_SECONDS, json.dumps([i.id for i in items]))
        return items

    async def add_pricing_tier(self, db: AsyncSession, service_id: str, data: PricingTierCreate) -> PricingTier:
        tier = PricingTier(service_id=service_id, name=data.name, description=data.description, price_cents=data.price_cents, features=json.dumps(data.features) if data.features else None, is_popular=data.is_popular)
        db.add(tier)
        await db.flush()
        return tier

    async def add_media(self, db: AsyncSession, service_id: str, data: ServiceMediaCreate) -> ServiceMedia:
        media = ServiceMedia(service_id=service_id, **data.model_dump())
        db.add(media)
        await db.flush()
        return media

    async def add_variant(self, db: AsyncSession, service_id: str, data: ServiceVariantCreate) -> ServiceVariant:
        variant = ServiceVariant(service_id=service_id, **data.model_dump())
        db.add(variant)
        await db.flush()
        return variant

catalog_service = CatalogService()
