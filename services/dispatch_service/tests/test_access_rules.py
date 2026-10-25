"""Providers report only their own location; assignment is admin-only."""

import pytest
import pytest_asyncio
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models.dispatch  # noqa: F401  (registers the models on Base.metadata)
from app.config import settings
from app.database import Base, get_db
from app.dependencies import get_booking_assigner
from app.main import app
from app.models.dispatch import DispatchJob


def auth(sub: str, role: str = "user", token_type: str = "access") -> dict:
    token = jwt.encode(
        {"sub": sub, "role": role, "type": token_type}, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return {"Authorization": f"Bearer {token}"}


ALICE, BOB, ADMIN = auth("alice"), auth("bob"), auth("ops", "admin")
ASSIGNED = []  # what booking_service was asked to record


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

    async def fake_assign(booking_id, provider_id, caller):
        if booking_id == "not-confirmed":
            raise HTTPException(status_code=409, detail="Invalid transition")
        ASSIGNED.append((booking_id, provider_id, caller.user_id))

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_booking_assigner] = lambda: fake_assign
    app.state.test_session_factory = factory
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_dispatch_rules(client):
    location = {"provider_id": "bob", "latitude": 18.52, "longitude": 73.85}
    assert (await client.post("/api/v1/providers/location", json=location)).status_code == 401
    assert (await client.post("/api/v1/providers/location", json=location, headers=ALICE)).status_code == 403
    assert (
        await client.post(
            "/api/v1/dispatch/assign",
            json={"booking_id": "b1", "booking_lat": 18.5, "booking_lon": 73.8, "providers": []},
            headers=ALICE,
        )
    ).status_code == 403
    assert (await client.get("/api/v1/providers/available", params={"lat": 18.5, "lon": 73.8})).status_code == 401
    assert (
        await client.get("/api/v1/providers/available", params={"lat": 18.5, "lon": 73.8}, headers=ALICE)
    ).status_code == 403


@pytest.mark.asyncio
async def test_dispatch_records_the_chosen_provider_on_the_booking(client):
    ASSIGNED.clear()
    body = {
        "booking_id": "b1",
        "booking_lat": 18.52,
        "booking_lon": 73.85,
        "providers": [
            {"provider_id": "far", "latitude": 19.0, "longitude": 72.8},
            {"provider_id": "near", "latitude": 18.53, "longitude": 73.86},
        ],
    }
    resp = await client.post("/api/v1/dispatch/assign", json=body, headers=ADMIN)
    assert resp.status_code == 200 and resp.json()["provider_id"] == "near"
    assert ASSIGNED == [("b1", "near", "ops")]

    # booking_service refusing (e.g. the booking is not CONFIRMED) fails the dispatch and keeps no job.
    refused = await client.post("/api/v1/dispatch/assign", json={**body, "booking_id": "not-confirmed"}, headers=ADMIN)
    assert refused.status_code == 409
    async with app.state.test_session_factory() as db:
        jobs = (await db.execute(select(DispatchJob.booking_id))).scalars().all()
    assert jobs == ["b1"]


@pytest.mark.asyncio
async def test_providers_cannot_report_a_position_that_is_not_on_earth(client):
    for lat, lon in ((91, 73.85), (-90.5, 73.85), (18.52, 180.1), (18.52, -999)):
        location = {"provider_id": "bob", "latitude": lat, "longitude": lon}
        assert (await client.post("/api/v1/providers/location", json=location, headers=BOB)).status_code == 422
    edge = {"provider_id": "bob", "latitude": -90, "longitude": 180}
    assert (await client.post("/api/v1/providers/location", json=edge, headers=BOB)).status_code == 200
    # Reporting for someone else is still refused, whatever the coordinates.
    other = {"provider_id": "alice", "latitude": 18.52, "longitude": 73.85}
    assert (await client.post("/api/v1/providers/location", json=other, headers=BOB)).status_code == 403
    nearby = await client.get("/api/v1/providers/available", params={"lat": 95, "lon": 73.8}, headers=ADMIN)
    assert nearby.status_code == 422
    assign = {"booking_id": "b1", "booking_lat": 18.5, "booking_lon": 73.8}
    bogus = [{"provider_id": "bob", "latitude": 18.5, "longitude": 500}]
    resp = await client.post("/api/v1/dispatch/assign", json={**assign, "providers": bogus}, headers=ADMIN)
    assert resp.status_code == 422
