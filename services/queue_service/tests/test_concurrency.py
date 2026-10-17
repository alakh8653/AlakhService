"""Taps that arrive at the same moment: the queue row is locked, so the line changes one request at a time.

The races need real row locks, so those tests run only when TEST_DATABASE_URL points at PostgreSQL (as in CI);
the unique index behind the lock is checked on SQLite too.
"""

import asyncio
import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.notifier import get_notifier
from app.database import Base, get_db
from app.dependencies import get_service_owner_lookup
from app.main import app
from app.models.queue import QueueEntry
from app.schemas.queue import QueueCreate, QueueJoinRequest
from app.services.queue_service import queue_service
from tests.helpers import ALICE, RecordingNotifier, auth, join
from tests.test_queue import db_session, engine  # noqa: F401  (fixtures)

TEST_DB = os.environ.get("TEST_DATABASE_URL", "")
needs_postgres = pytest.mark.skipif(not TEST_DB.startswith("postgresql"), reason="row locks need PostgreSQL")


@pytest_asyncio.fixture
async def pg_client():
    """The app on TEST_DATABASE_URL, each request on its own connection, as in production."""
    pg_engine = create_async_engine(TEST_DB, poolclass=NullPool)
    async with pg_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(pg_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def fake_owner(service_id):
        return "alice"

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_service_owner_lookup] = lambda: fake_owner
    app.dependency_overrides[get_notifier] = RecordingNotifier
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
    async with pg_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await pg_engine.dispose()


async def _open_queue(client, **settings):
    resp = await client.post("/api/v1/queues", json={"service_id": "svc-1", **settings}, headers=ALICE)
    return resp.json()["id"]


def _join(client, qid, who):
    return client.post(
        f"/api/v1/queues/{qid}/join", json={"customer_id": who, "service_id": "svc-1"}, headers=auth(who)
    )


@needs_postgres
@pytest.mark.asyncio
async def test_a_customer_tapping_join_many_times_at_once_holds_one_place(pg_client):
    client = pg_client
    qid = await _open_queue(client)
    replies = await asyncio.gather(*[_join(client, qid, "c1") for _ in range(10)])
    assert {r.status_code for r in replies} == {201}
    assert len({r.json()["id"] for r in replies}) == 1
    assert (await client.get(f"/api/v1/queues/{qid}", headers=ALICE)).json()["current_size"] == 1


@needs_postgres
@pytest.mark.asyncio
async def test_simultaneous_joins_do_not_overfill_the_queue(pg_client):
    client = pg_client
    qid = await _open_queue(client, max_capacity=3)
    replies = await asyncio.gather(*[_join(client, qid, f"c{i}") for i in range(10)])
    assert sorted(r.status_code for r in replies) == [201] * 3 + [409] * 7
    assert (await client.get(f"/api/v1/queues/{qid}", headers=ALICE)).json()["current_size"] == 3


@needs_postgres
@pytest.mark.asyncio
async def test_two_next_taps_at_once_call_two_different_customers(pg_client):
    client = pg_client
    qid = await _open_queue(client)
    for who in ("c1", "c2", "c3"):
        await join(client, qid, who)
    replies = await asyncio.gather(*[client.post(f"/api/v1/queues/{qid}/next", headers=ALICE) for _ in range(2)])
    assert sorted(r.json()["customer_id"] for r in replies) == ["c1", "c2"]
    assert (await client.get(f"/api/v1/queues/{qid}", headers=ALICE)).json()["current_size"] == 1


@pytest.mark.asyncio
async def test_a_customer_being_served_who_joins_again_keeps_their_turn(client):
    qid = await _open_queue(client)
    first = await join(client, qid, "c1")
    await client.post(f"/api/v1/queues/{qid}/next", headers=ALICE)
    again = (await _join(client, qid, "c1")).json()
    assert (again["id"], again["status"]) == (first["id"], "CALLED")


@pytest.mark.anyio
async def test_the_database_refuses_a_second_open_entry_for_the_same_customer(db_session):  # noqa: F811
    q = await queue_service.create_queue(db_session, QueueCreate(service_id="svc-1"))
    held = await queue_service.join_queue(db_session, q.id, QueueJoinRequest(customer_id="c1", service_id="svc-1"))
    held.status = "SERVED"  # finished entries do not count: the customer may queue again
    again = await queue_service.join_queue(db_session, q.id, QueueJoinRequest(customer_id="c1", service_id="svc-1"))
    dup = QueueEntry(queue_id=q.id, customer_id="c1", service_id="svc-1", status="CALLED")
    db_session.add(dup)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()
    assert again.id != held.id


@pytest.mark.anyio
async def test_a_join_that_slips_past_the_lock_returns_the_place_already_held(db_session, monkeypatch):  # noqa: F811
    q = await queue_service.create_queue(db_session, QueueCreate(service_id="svc-1"))
    held = await queue_service.join_queue(db_session, q.id, QueueJoinRequest(customer_id="c1", service_id="svc-1"))
    # As if a concurrent join had committed after this request looked for the customer's place.
    real = queue_service._held_place
    misses = iter([None])

    async def stale_then_real(db, queue, customer_id):
        return next(misses, None) or await real(db, queue, customer_id)

    monkeypatch.setattr(queue_service, "_held_place", stale_then_real)
    again = await queue_service.join_queue(db_session, q.id, QueueJoinRequest(customer_id="c1", service_id="svc-1"))
    assert again.id == held.id
    entries = (await db_session.execute(select(QueueEntry).where(QueueEntry.customer_id == "c1"))).scalars().all()
    assert len(entries) == 1
    assert (await queue_service.get_queue(db_session, q.id)).current_size == 1
