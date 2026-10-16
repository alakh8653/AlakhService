"""The `client` fixture: the app on an in-memory database, with a fake shop owner and notifier."""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models.queue  # noqa: F401  (registers the models on Base.metadata)
from app.core.notifier import get_notifier
from app.database import Base, get_db
from app.dependencies import get_service_owner_lookup
from app.main import app
from tests.helpers import CALLED, RecordingNotifier


@pytest_asyncio.fixture
async def client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            yield session
            await session.commit()

    app.dependency_overrides[get_db] = override_get_db
    owners = {"svc-1": "alice"}

    async def fake_owner(service_id):
        return owners.get(service_id)

    app.dependency_overrides[get_service_owner_lookup] = lambda: fake_owner
    app.dependency_overrides[get_notifier] = RecordingNotifier
    CALLED.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
    await engine.dispose()
