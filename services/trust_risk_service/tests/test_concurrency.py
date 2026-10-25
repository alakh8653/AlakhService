"""Signals for one user that arrive at the same moment are all counted, and none fails.

The races need real row locks, so the concurrent tests run only when TEST_DATABASE_URL points at PostgreSQL
(as in CI); creating the profile only once, without errors, is checked on SQLite too.
"""

import asyncio
import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.database import Base, get_db
from app.main import app
from tests.test_access_rules import ADMIN, client  # noqa: F401  (fixture)

TEST_DB = os.environ.get("TEST_DATABASE_URL", "")
needs_postgres = pytest.mark.skipif(not TEST_DB.startswith("postgresql"), reason="row locks need PostgreSQL")


@pytest_asyncio.fixture
async def pg_client():
    """The app on TEST_DATABASE_URL, each request on its own connection, as in production."""
    engine = create_async_engine(TEST_DB, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


def _signal(http, user_id, risky=True):
    body = {"signal_type": "chargeback", "value": 1.0, "is_risk_event": risky}
    return http.post(f"/api/v1/risk/{user_id}/signal", json=body, headers=ADMIN)


@needs_postgres
@pytest.mark.asyncio
async def test_the_first_signals_for_a_new_user_all_succeed_and_are_all_counted(pg_client):
    replies = await asyncio.gather(*[_signal(pg_client, "new-user") for _ in range(10)])
    assert {r.status_code for r in replies} == {200}
    profile = (await pg_client.get("/api/v1/risk/new-user", headers=ADMIN)).json()
    assert profile["risk_events"] == 10
    assert len((await pg_client.get("/api/v1/risk/new-user/history", headers=ADMIN)).json()) == 10


@needs_postgres
@pytest.mark.asyncio
async def test_simultaneous_risk_and_safe_signals_are_all_counted(pg_client):
    await pg_client.get("/api/v1/risk/known-user", headers=ADMIN)
    replies = await asyncio.gather(*[_signal(pg_client, "known-user", risky=i % 2 == 0) for i in range(10)])
    assert {r.status_code for r in replies} == {200}
    profile = (await pg_client.get("/api/v1/risk/known-user", headers=ADMIN)).json()
    assert (profile["risk_events"], profile["safe_events"]) == (5, 5)


@pytest.mark.asyncio
async def test_first_signals_for_a_new_user_at_once_create_one_profile_without_errors(client):  # noqa: F811
    replies = await asyncio.gather(*[_signal(client, "new-user") for _ in range(10)])
    assert {r.status_code for r in replies} == {200}
    assert len({r.json()["id"] for r in replies}) == 1
