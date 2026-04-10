import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.models.service import Service
from app.schemas.service import ServiceCreate, ServiceUpdate


async def get_service(db: AsyncSession, service_id: uuid.UUID) -> Service:
    result = await db.execute(select(Service).where(Service.id == service_id))
    service = result.scalar_one_or_none()
    if not service:
        raise NotFoundException(resource_name="Service")
    return service


async def get_services(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    category: str | None = None,
) -> list[Service]:
    stmt = select(Service).where(Service.is_active)
    if category:
        stmt = stmt.where(Service.category == category)
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_service(db: AsyncSession, service_create: ServiceCreate) -> Service:
    service = Service(**service_create.model_dump())
    db.add(service)
    await db.flush()
    await db.refresh(service)
    return service


async def update_service(
    db: AsyncSession, service_id: uuid.UUID, service_update: ServiceUpdate
) -> Service:
    service = await get_service(db, service_id)
    update_data = service_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(service, field, value)
    await db.flush()
    await db.refresh(service)
    return service


async def delete_service(db: AsyncSession, service_id: uuid.UUID) -> None:
    service = await get_service(db, service_id)
    service.is_active = False
    await db.flush()
