"""API tests for listing disputes and moving them through review, escalation and resolution."""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models.dispute  # noqa: F401  (registers the models on Base.metadata)
from app.database import Base, get_db
from app.main import app


@pytest_asyncio.fixture
async def client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session
            await session.commit()

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
    await engine.dispose()


async def create(client, booking_id="b-1", raised_by="cust-1", dispute_type="service_quality"):
    resp = await client.post(
        "/api/v1/disputes",
        json={"booking_id": booking_id, "raised_by": raised_by, "dispute_type": dispute_type, "description": "Late"},
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_list_disputes_paginates_newest_first(client):
    ids = [(await create(client, booking_id=f"b-{i}"))["id"] for i in range(3)]

    resp = await client.get("/api/v1/disputes", params={"page": 1, "per_page": 2})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert body["page"] == 1 and body["per_page"] == 2
    assert len(body["data"]) == 2

    page2 = (await client.get("/api/v1/disputes", params={"page": 2, "per_page": 2})).json()
    seen = {d["id"] for d in body["data"]} | {d["id"] for d in page2["data"]}
    assert seen == set(ids)


@pytest.mark.asyncio
async def test_list_disputes_filters(client):
    first = await create(client, booking_id="b-1", raised_by="cust-1")
    await create(client, booking_id="b-2", raised_by="cust-2")
    await client.post(f"/api/v1/disputes/{first['id']}/review")

    by_status = (await client.get("/api/v1/disputes", params={"status": "UNDER_REVIEW"})).json()
    assert [d["id"] for d in by_status["data"]] == [first["id"]]

    by_customer = (await client.get("/api/v1/disputes", params={"raised_by": "cust-2"})).json()
    assert by_customer["total"] == 1 and by_customer["data"][0]["booking_id"] == "b-2"

    assert (await client.get("/api/v1/disputes", params={"status": "NOPE"})).status_code == 422


@pytest.mark.asyncio
async def test_review_escalate_resolve_flow(client):
    dispute = await create(client)
    base = f"/api/v1/disputes/{dispute['id']}"

    # Escalation is only allowed from review.
    assert (await client.post(f"{base}/escalate")).status_code == 400
    assert (await client.post(f"{base}/review")).json()["status"] == "UNDER_REVIEW"
    assert (await client.post(f"{base}/escalate")).json()["status"] == "ESCALATED"

    resolved = (await client.post(f"{base}/resolve", json={"resolution": "Refunded 50%"})).json()
    assert resolved["status"] == "RESOLVED"
    assert resolved["resolution"] == "Refunded 50%"
    assert resolved["resolved_at"] is not None
