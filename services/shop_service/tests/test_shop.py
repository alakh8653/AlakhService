import os
import sys

import pytest
import pytest_asyncio

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.exceptions import ShopNotFoundError
from app.database import Base
from app.schemas.shop import ShopCreate, ShopUpdate
from app.services.shop_service import ShopService

pytest_plugins = ("anyio",)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine):
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
def service():
    return ShopService()


@pytest.mark.anyio
async def test_create_shop(db_session, service):
    data = ShopCreate(owner_id="owner-1", name="Test Shop", category="salon", city="Mumbai")
    shop = await service.create_shop(db_session, data)
    assert shop.id is not None
    assert shop.name == "Test Shop"
    assert shop.category == "salon"
    assert shop.is_active is True
    assert shop.is_verified is False
    assert shop.rating_avg == 0.0


@pytest.mark.anyio
async def test_create_shop_keeps_its_contact_details_and_location(db_session, service):
    # Customers get directions to the address/position and call the phone; none may be dropped.
    data = ShopCreate(
        owner_id="owner-1",
        name="Asha Salon",
        category="salon",
        city="Pune",
        address="12 MG Road",
        phone="+919876543210",
        email="asha@example.com",
        latitude=18.5204,
        longitude=73.8567,
    )
    shop = await service.create_shop(db_session, data)
    assert (shop.address, shop.phone, shop.email) == ("12 MG Road", "+919876543210", "asha@example.com")
    assert (shop.latitude, shop.longitude) == (18.5204, 73.8567)


@pytest.mark.anyio
async def test_search_shops_by_city(db_session, service):
    await service.create_shop(db_session, ShopCreate(owner_id="o1", name="Mumbai Shop", category="spa", city="Mumbai"))
    await service.create_shop(db_session, ShopCreate(owner_id="o2", name="Delhi Shop", category="spa", city="Delhi"))
    results = await service.search_shops(db_session, city="Mumbai")
    assert len(results) == 1
    assert results[0].city == "Mumbai"


@pytest.mark.anyio
async def test_search_shops_by_category(db_session, service):
    await service.create_shop(db_session, ShopCreate(owner_id="o1", name="Salon A", category="salon", city="Pune"))
    await service.create_shop(db_session, ShopCreate(owner_id="o2", name="Spa B", category="spa", city="Pune"))
    results = await service.search_shops(db_session, category="salon")
    assert all(s.category == "salon" for s in results)


@pytest.mark.anyio
async def test_update_shop(db_session, service):
    shop = await service.create_shop(db_session, ShopCreate(owner_id="o1", name="Old Name", category="salon"))
    updated = await service.update_shop(db_session, shop.id, ShopUpdate(name="New Name"))
    assert updated.name == "New Name"


@pytest.mark.anyio
async def test_update_rating(db_session, service):
    shop = await service.create_shop(db_session, ShopCreate(owner_id="o1", name="Rated Shop", category="salon"))
    await service.update_rating(db_session, shop.id, 4.0)
    shop = await service.update_rating(db_session, shop.id, 5.0)
    assert shop.rating_count == 2
    assert shop.rating_avg == 4.5


@pytest.mark.anyio
async def test_get_shop_not_found(db_session, service):
    with pytest.raises(ShopNotFoundError):
        await service.get_shop(db_session, "non-existent-id")
