import pytest
import pytest_asyncio
import os
import sys

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.database import Base
from app.services.catalog_service import CatalogService
from app.schemas.catalog import CategoryCreate, ServiceListingCreate, ServiceListingUpdate
from app.core.search import TFIDFIndex, BKTree, levenshtein_distance
from app.core.exceptions import ServiceListingNotFoundError

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
    return CatalogService()


@pytest.mark.anyio
async def test_levenshtein_distance():
    assert levenshtein_distance("kitten", "sitting") == 3
    assert levenshtein_distance("", "") == 0
    assert levenshtein_distance("abc", "abc") == 0
    assert levenshtein_distance("a", "b") == 1
    assert levenshtein_distance("massage", "massag") == 1


@pytest.mark.anyio
async def test_tfidf_search():
    index = TFIDFIndex()
    index.add_document("d1", "haircut and styling for men")
    index.add_document("d2", "deep tissue massage therapy")
    index.add_document("d3", "haircut and beard trim")

    results = index.search("haircut men")
    assert len(results) > 0
    ids = [r[0] for r in results]
    assert "d1" in ids or "d3" in ids


@pytest.mark.anyio
async def test_tfidf_removes_document():
    index = TFIDFIndex()
    index.add_document("d1", "manicure pedicure nails")
    index.add_document("d2", "hair coloring highlights")
    index.remove_document("d1")
    results = index.search("manicure")
    ids = [r[0] for r in results]
    assert "d1" not in ids


@pytest.mark.anyio
async def test_bktree_fuzzy_matching():
    tree = BKTree()
    for word in ["massage", "massage therapy", "hairdresser", "haircut", "manicure", "pedicure"]:
        for w in word.split():
            tree.add(w)

    results = tree.search("masage", max_distance=2)  # typo
    terms = [r[0] for r in results]
    assert "massage" in terms


@pytest.mark.anyio
async def test_bktree_exact_match():
    tree = BKTree()
    tree.add("haircut")
    results = tree.search("haircut", max_distance=0)
    assert len(results) == 1
    assert results[0][0] == "haircut"
    assert results[0][1] == 0


@pytest.mark.anyio
async def test_create_category(db_session, service):
    cat = await service.create_category(db_session, CategoryCreate(name="Beauty", slug="beauty", description="Beauty services"))
    assert cat.id is not None
    assert cat.name == "Beauty"
    assert cat.slug == "beauty"


@pytest.mark.anyio
async def test_create_service(db_session, service):
    svc = await service.create_service(db_session, ServiceListingCreate(
        shop_id="shop-1", name="Deep Tissue Massage", description="Relaxing massage", price_cents=5000, duration_minutes=60
    ))
    assert svc.id is not None
    assert svc.name == "Deep Tissue Massage"
    assert svc.price_cents == 5000


@pytest.mark.anyio
async def test_search_services_tfidf(db_session, service):
    await service.create_service(db_session, ServiceListingCreate(shop_id="shop-1", name="Swedish Massage Therapy", description="Relaxing full body massage", price_cents=4000))
    await service.create_service(db_session, ServiceListingCreate(shop_id="shop-1", name="Haircut and Styling", description="Professional hair services", price_cents=1500))

    results = await service.search_services(db_session, q="massage therapy")
    assert len(results) >= 1
    names = [r.name for r in results]
    assert any("Massage" in n for n in names)


@pytest.mark.anyio
async def test_update_service(db_session, service):
    svc = await service.create_service(db_session, ServiceListingCreate(shop_id="s1", name="Basic Manicure", price_cents=1000))
    updated = await service.update_service(db_session, svc.id, ServiceListingUpdate(price_cents=1200, name="Premium Manicure"))
    assert updated.price_cents == 1200
    assert updated.name == "Premium Manicure"


@pytest.mark.anyio
async def test_service_not_found(db_session, service):
    with pytest.raises(ServiceListingNotFoundError):
        await service.get_service(db_session, "nonexistent-id")
