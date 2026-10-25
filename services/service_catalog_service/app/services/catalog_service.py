import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional

import structlog
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ServiceListingNotFoundError
from app.core.search import BKTree, TFIDFIndex
from app.models.catalog import ServiceCategory, ServiceListing
from app.schemas.catalog import CategoryCreate, ServiceListingCreate, ServiceListingUpdate

log = structlog.get_logger()

# In-memory search indices. They live per process, so each process rebuilds them from the
# database before its first search (see _ensure_index) and keeps them current on writes.
_tfidf_index = TFIDFIndex()
_bk_tree = BKTree()
_index_state = {"loaded": False}


def _index_listing(service: ServiceListing) -> None:
    if not service.is_active:
        _tfidf_index.remove_document(service.id)
        return
    _tfidf_index.add_document(service.id, f"{service.name} {service.description or ''}")
    # Add name tokens to BK-tree for fuzzy search
    for word in service.name.lower().split():
        if len(word) >= 2:
            _bk_tree.add(word)


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

    async def create_service(
        self, db: AsyncSession, data: ServiceListingCreate, shop_listed: bool = True
    ) -> ServiceListing:
        service = ServiceListing(
            id=str(uuid.uuid4()),
            category_id=data.category_id,
            shop_id=data.shop_id,
            name=data.name,
            description=data.description,
            price_cents=data.price_cents,
            duration_minutes=data.duration_minutes,
            tags=json.dumps(data.tags) if data.tags else None,
            service_modes=",".join(data.service_modes),
            home_visit_fee_cents=data.home_visit_fee_cents,
            pickup_fee_cents=data.pickup_fee_cents,
            is_active=True,
            shop_listed=shop_listed,
            created_at=datetime.now(timezone.utc),
        )
        db.add(service)
        await db.flush()

        _index_listing(service)
        log.info("service_created", service_id=service.id, name=data.name)
        return service

    async def get_service(self, db: AsyncSession, service_id: str) -> ServiceListing:
        result = await db.execute(select(ServiceListing).where(ServiceListing.id == service_id))
        service = result.scalar_one_or_none()
        if not service:
            raise ServiceListingNotFoundError()
        return service

    async def list_services(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 20,
        shop_id: Optional[str] = None,
        include_inactive: bool = False,
    ) -> List[ServiceListing]:
        query = select(ServiceListing)
        if shop_id:
            # A shop's own list (its dashboard) includes services of a shop still awaiting approval.
            query = query.where(ServiceListing.shop_id == shop_id)
        else:
            query = query.where(ServiceListing.shop_listed == True)
        if not include_inactive:
            query = query.where(ServiceListing.is_active == True)
        result = await db.execute(query.order_by(ServiceListing.name, ServiceListing.id).offset(skip).limit(limit))
        return list(result.scalars().all())

    async def _ensure_index(self, db: AsyncSession) -> None:
        if _index_state["loaded"]:
            return
        result = await db.execute(select(ServiceListing).where(ServiceListing.is_active == True))
        _tfidf_index.clear()
        for service in result.scalars().all():
            _index_listing(service)
        _index_state["loaded"] = True
        log.info("search_index_built")

    async def search_services(
        self, db: AsyncSession, q: Optional[str] = None, category: Optional[str] = None, limit: int = 20
    ) -> List[ServiceListing]:
        base = select(ServiceListing).where(ServiceListing.is_active == True, ServiceListing.shop_listed == True)
        if category:
            base = base.where(ServiceListing.category_id == category)
        if q:
            await self._ensure_index(db)
            # Only listings that contain a query term, best match first.
            ranked = [doc_id for doc_id, _ in _tfidf_index.search(q, top_k=None)]
            if ranked:
                result = await db.execute(base.where(ServiceListing.id.in_(ranked)))
                by_id = {s.id: s for s in result.scalars().all()}
                return [by_id[i] for i in ranked if i in by_id][:limit]
            # Fallback to LIKE search (substrings and words the tokenizer drops)
            base = base.where(or_(ServiceListing.name.ilike(f"%{q}%"), ServiceListing.description.ilike(f"%{q}%")))
        result = await db.execute(base.order_by(ServiceListing.name, ServiceListing.id).limit(limit))
        return list(result.scalars().all())

    async def update_service(self, db: AsyncSession, service_id: str, data: ServiceListingUpdate) -> ServiceListing:
        service = await self.get_service(db, service_id)
        update_data = data.model_dump(exclude_unset=True)
        if "tags" in update_data and update_data["tags"] is not None:
            update_data["tags"] = json.dumps(update_data["tags"])
        if update_data.get("service_modes") is not None:
            update_data["service_modes"] = ",".join(update_data["service_modes"])
        for fee in ("name", "price_cents", "is_active", "home_visit_fee_cents", "pickup_fee_cents", "service_modes"):
            if fee in update_data and update_data[fee] is None:
                del update_data[fee]  # these columns are never null
        for field, value in update_data.items():
            setattr(service, field, value)
        await db.flush()
        # Re-index so search matches the new name/description and stops returning deactivated listings.
        _index_listing(service)
        log.info("service_updated", service_id=service_id)
        return service

    async def set_shop_listed(self, db: AsyncSession, shop_id: str, listed: bool) -> int:
        """Shows or hides every service of a shop in browsing and search. Returns how many changed."""
        result = await db.execute(
            update(ServiceListing)
            .where(ServiceListing.shop_id == shop_id, ServiceListing.shop_listed != listed)
            .values(shop_listed=listed)
        )
        log.info("shop_listing_changed", shop_id=shop_id, listed=listed, services=result.rowcount)
        return result.rowcount


catalog_service = CatalogService()
