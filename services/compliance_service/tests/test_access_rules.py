"""GDPR requests and consent records are the user's own (or an admin's to manage)."""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models.compliance  # noqa: F401  (registers the models on Base.metadata)
from app.config import settings
from app.database import Base, get_db
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
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_users_manage_only_their_own_data(client):
    assert (await client.post("/api/v1/gdpr/export", json={"user_id": "alice"})).status_code == 401
    assert (await client.post("/api/v1/gdpr/export", json={"user_id": "bob"}, headers=ALICE)).status_code == 403
    assert (await client.post("/api/v1/gdpr/erasure", json={"user_id": "bob"}, headers=ALICE)).status_code == 403
    assert (await client.get("/api/v1/consent/bob", headers=ALICE)).status_code == 403

    export = await client.post("/api/v1/gdpr/export", json={"user_id": "alice"}, headers=ALICE)
    assert export.status_code == 201
    url = f"/api/v1/gdpr/export/{export.json()['id']}"
    assert (await client.get(url, headers=ALICE)).status_code == 200
    assert (await client.get(url, headers=BOB)).status_code == 404
    assert (await client.get(url, headers=ADMIN)).status_code == 200
    assert (await client.get("/api/v1/consent/alice", headers=ALICE)).status_code == 200
