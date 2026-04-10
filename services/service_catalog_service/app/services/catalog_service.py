import uuid
import json
from datetime import datetime, timezone
from typing import List, Optional
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.models.catalog import ServiceCategory, ServiceListing, ServiceTag
from app.schemas.catalog import CategoryCreate, ServiceListingCreate, ServiceListingUpdate
from app.core.search import TFIDFIndex, BKTree
from app.core.exceptions import ServiceListingNotFoundError, CategoryNotFoundError

log = structlog.get_logger()

# In-memory search indices
_tfidf_index = TFIDFIndex()
_bk_tree = BKTree()


class CatalogService:

    async def create_category(self, db: AsyncSession, data: CategoryCreate) -> ServiceCategory:
        cat = ServiceCategory(
            id=str(uuid.uuid4()),
            name=data.name,
            slug=data.slug,
            parent_id=data.parent_id,
            description=data.description,
            is_active=True,
        )
        db.add(cat)
        await db.flush()
        log.info("category_created", category_id=cat.id, name=cat.name)
        return cat

    async def list_categories(self, db: AsyncSession) -> List[ServiceCategory]:
        result = await db.execute(select(ServiceCategory).where(ServiceCategory.is_active == True))
        return list(result.scalars().all())

    async def create_service(self, db: AsyncSession, data: ServiceListingCreate) -> ServiceListing:
        service = ServiceListing(
            id=str(uuid.uuid4()),
            category_id=data.category_id,
            shop_id=data.shop_id,
            name=data.name,
            description=data.description,
            price_cents=data.price_cents,
            duration_minutes=data.duration_minutes,
            tags=json.dumps(data.tags) if data.tags else None,
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        db.add(service)
        await db.flush()

        # Index in TF-IDF
        doc_text = f"{data.name} {data.description or ''}"
        _tfidf_index.add_document(service.id, doc_text)

        # Add name tokens to BK-tree for fuzzy search
        for word in data.name.lower().split():
            if len(word) >= 2:
                _bk_tree.add(word)

        log.info("service_created", service_id=service.id, name=data.name)
        return service

    async def get_service(self, db: AsyncSession, service_id: str) -> ServiceListing:
        result = await db.execute(select(ServiceListing).where(ServiceListing.id == service_id))
        service = result.scalar_one_or_none()
        if not service:
            raise ServiceListingNotFoundError()
        return service

    async def list_services(self, db: AsyncSession, skip: int = 0, limit: int = 20) -> List[ServiceListing]:
        result = await db.execute(select(ServiceListing).where(ServiceListing.is_active == True).offset(skip).limit(limit))
        return list(result.scalars().all())

    async def search_services(self, db: AsyncSession, q: Optional[str] = None, category: Optional[str] = None) -> List[ServiceListing]:
        if q:
            # TF-IDF search
            tfidf_results = _tfidf_index.search(q, top_k=20)
            if tfidf_results:
                ids = [r[0] for r in tfidf_results]
                stmt = select(ServiceListing).where(ServiceListing.id.in_(ids), ServiceListing.is_active == True)
                if category:
                    stmt = stmt.where(ServiceListing.category_id == category)
                result = await db.execute(stmt)
                return list(result.scalars().all())
            else:
                # Fallback to LIKE search
                stmt = select(ServiceListing).where(
                    ServiceListing.is_active == True,
                    or_(ServiceListing.name.ilike(f"%{q}%"), ServiceListing.description.ilike(f"%{q}%"))
                )
                if category:
                    stmt = stmt.where(ServiceListing.category_id == category)
                result = await db.execute(stmt)
                return list(result.scalars().all())
        else:
            stmt = select(ServiceListing).where(ServiceListing.is_active == True)
            if category:
                stmt = stmt.where(ServiceListing.category_id == category)
            result = await db.execute(stmt)
            return list(result.scalars().all())

    async def update_service(self, db: AsyncSession, service_id: str, data: ServiceListingUpdate) -> ServiceListing:
        service = await self.get_service(db, service_id)
        update_data = data.model_dump(exclude_unset=True)
        if "tags" in update_data and update_data["tags"] is not None:
            update_data["tags"] = json.dumps(update_data["tags"])
        for field, value in update_data.items():
            setattr(service, field, value)
        await db.flush()
        log.info("service_updated", service_id=service_id)
        return service


catalog_service = CatalogService()
