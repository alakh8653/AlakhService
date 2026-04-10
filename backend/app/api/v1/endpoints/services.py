from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_active_user, get_current_superuser
from app.models.user import User
from app.schemas.service import ServiceCreate, ServiceRead, ServiceUpdate
from app.services import service_service
from app.api.v1.dependencies import pagination_params

router = APIRouter()


@router.get("/", response_model=list[ServiceRead])
async def list_services(
    pagination: dict = Depends(pagination_params),
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List all active services with optional category filter."""
    return await service_service.get_services(
        db, skip=pagination["skip"], limit=pagination["limit"], category=category
    )


@router.get("/{service_id}", response_model=ServiceRead)
async def get_service(service_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a service by ID."""
    return await service_service.get_service(db, service_id)


@router.post("/", response_model=ServiceRead, status_code=status.HTTP_201_CREATED)
async def create_service(
    service_create: ServiceCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
):
    """Create a new service (admin only)."""
    return await service_service.create_service(db, service_create)


@router.put("/{service_id}", response_model=ServiceRead)
async def update_service(
    service_id: UUID,
    service_update: ServiceUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
):
    """Update an existing service (admin only)."""
    return await service_service.update_service(db, service_id, service_update)


@router.delete("/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_service(
    service_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
):
    """Delete a service (admin only)."""
    await service_service.delete_service(db, service_id)
