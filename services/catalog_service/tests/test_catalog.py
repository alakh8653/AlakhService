import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.catalog_service import CatalogService
from app.core.exceptions import ServiceNotFoundError, SlugConflictError

@pytest.mark.asyncio
async def test_get_service_not_found():
    svc = CatalogService()
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=mock_result)
    with pytest.raises(ServiceNotFoundError):
        await svc.get_service(db, "nonexistent-id")

@pytest.mark.asyncio
async def test_create_category_slug_conflict():
    svc = CatalogService()
    db = AsyncMock()
    existing = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing
    db.execute = AsyncMock(return_value=mock_result)
    from app.schemas.catalog import ServiceCategoryCreate
    with pytest.raises(SlugConflictError):
        await svc.create_category(db, ServiceCategoryCreate(name="Test", slug="test-slug"))

@pytest.mark.asyncio
async def test_list_categories_empty():
    svc = CatalogService()
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=mock_result)
    result = await svc.list_categories(db)
    assert result == []
