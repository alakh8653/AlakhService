"""Queues are opened by the service's shop owner; customers join and leave as themselves."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models.queue  # noqa: F401  (registers the models on Base.metadata)
from app.config import settings
from app.core.notifier import get_notifier
from app.database import Base, get_db
from app.dependencies import get_service_owner_lookup
from app.main import app


def auth(sub: str, role: str = "user", token_type: str = "access") -> dict:
    token = jwt.encode(
        {"sub": sub, "role": role, "type": token_type}, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return {"Authorization": f"Bearer {token}"}


ALICE, BOB, ADMIN = auth("alice"), auth("bob"), auth("ops", "admin")
CALLED: list = []


class RecordingNotifier:
    async def send(self, event, recipients, data):
        CALLED.append((event, [r["user_id"] for r in recipients]))


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


@pytest.mark.asyncio
async def test_customers_can_find_a_services_open_queues(client):
    created = await client.post("/api/v1/queues", json={"service_id": "svc-1"}, headers=ALICE)
    assert (await client.get("/api/v1/queues", params={"service_id": "svc-1"})).status_code == 401
    found = await client.get("/api/v1/queues", params={"service_id": "svc-1"}, headers=BOB)
    assert [q["id"] for q in found.json()] == [created.json()["id"]]
    assert (await client.get("/api/v1/queues", params={"service_id": "other"}, headers=BOB)).json() == []


async def join(client, qid, who):
    resp = await client.post(
        f"/api/v1/queues/{qid}/join", json={"customer_id": who, "service_id": "svc-1"}, headers=auth(who)
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_positions_move_up_as_people_ahead_are_served_or_leave(client):
    qid = (await client.post("/api/v1/queues", json={"service_id": "svc-1"}, headers=ALICE)).json()["id"]
    first, second, third = [await join(client, qid, who) for who in ("c1", "c2", "c3")]
    assert [first["position"], second["position"], third["position"]] == [1, 2, 3]
    assert third["estimated_wait_minutes"] == 10
    # Joining again keeps your place instead of queueing twice.
    assert (await join(client, qid, "c2"))["id"] == second["id"]

    pos = lambda who: client.get(f"/api/v1/queues/{qid}/position/{who}", headers=auth(who))  # noqa: E731
    called = await client.post(f"/api/v1/queues/{qid}/next", headers=ALICE)
    assert called.json()["customer_id"] == "c1"
    assert CALLED == [("queue.called", ["c1"])]
    assert (await pos("c1")).status_code == 404  # no longer waiting
    assert (await pos("c3")).json()["position"] == 2

    await client.delete(f"/api/v1/queues/{qid}/entries/{second['id']}", headers=auth("c2"))
    assert (await pos("c3")).json() == {
        "customer_id": "c3",
        "queue_id": qid,
        "position": 1,
        "estimated_wait_minutes": 0,
    }
    waiting = (await client.get(f"/api/v1/queues/{qid}/entries", headers=ALICE)).json()
    assert [(e["customer_id"], e["position"]) for e in waiting] == [("c3", 1)]
    assert (await client.get(f"/api/v1/queues/{qid}", headers=BOB)).json()["current_size"] == 1

    await client.post(f"/api/v1/queues/{qid}/next", headers=ALICE)
    assert (await client.post(f"/api/v1/queues/{qid}/next", headers=ALICE)).json() is None


@pytest.mark.asyncio
async def test_only_the_shop_manages_its_queue(client):
    qid = (await client.post("/api/v1/queues", json={"service_id": "svc-1"}, headers=ALICE)).json()["id"]
    await join(client, qid, "c1")
    assert (await client.get(f"/api/v1/queues/{qid}/entries", headers=BOB)).status_code == 403
    assert (await client.post(f"/api/v1/queues/{qid}/next", headers=BOB)).status_code == 403
    assert (await client.patch(f"/api/v1/queues/{qid}", json={"is_accepting": False}, headers=BOB)).status_code == 403
    assert CALLED == []

    assert (await client.post("/api/v1/queues", json={"service_id": "svc-1"}, headers=ALICE)).status_code == 409
    closed = await client.patch(f"/api/v1/queues/{qid}", json={"is_accepting": False}, headers=ALICE)
    assert closed.json()["is_accepting"] is False
    late = await client.post(
        f"/api/v1/queues/{qid}/join", json={"customer_id": "c9", "service_id": "svc-1"}, headers=auth("c9")
    )
    assert late.status_code == 409
    # Customers no longer find it, but the shop still sees it to reopen.
    assert (await client.get("/api/v1/queues", params={"service_id": "svc-1"}, headers=BOB)).json() == []
    every = await client.get("/api/v1/queues", params={"service_id": "svc-1", "include_closed": True}, headers=ALICE)
    assert [q["id"] for q in every.json()] == [qid]
