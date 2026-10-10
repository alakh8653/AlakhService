"""Queues are opened by the service's shop owner; customers join and leave as themselves."""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models.queue  # noqa: F401  (registers the models on Base.metadata)
from app.config import settings
from app.database import Base, get_db
from app.dependencies import get_service_owner_lookup
from app.main import app


def auth(sub: str, role: str = "user", token_type: str = "access") -> dict:
    token = jwt.encode({"sub": sub, "role": role, "type": token_type}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {"Authorization": f"Bearer {token}"}


ALICE, BOB, ADMIN = auth("alice"), auth("bob"), auth("ops", "admin")


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
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_queue_rules(client):
    assert (await client.post("/api/v1/queues", json={"service_id": "svc-1"})).status_code == 401
    assert (await client.post("/api/v1/queues", json={"service_id": "svc-1"}, headers=BOB)).status_code == 403
    assert (await client.post("/api/v1/queues", json={"service_id": "missing"}, headers=BOB)).status_code == 404
    queue = await client.post("/api/v1/queues", json={"service_id": "svc-1"}, headers=ALICE)
    assert queue.status_code == 201
    qid = queue.json()["id"]

    join = {"customer_id": "alice", "service_id": "svc-1"}
    assert (await client.post(f"/api/v1/queues/{qid}/join", json=join, headers=BOB)).status_code == 403
    assert (await client.get(f"/api/v1/queues/{qid}/position/alice", headers=BOB)).status_code == 403
    assert (await client.delete(f"/api/v1/queues/{qid}/entries/someone-elses", headers=BOB)).status_code == 404
