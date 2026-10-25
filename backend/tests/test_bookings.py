import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service import Service
from app.models.user import User


@pytest.mark.asyncio
async def test_create_booking(client: AsyncClient, test_user: User, auth_headers: dict, db: AsyncSession):
    service = Service(name="Test Svc", category="test", price=100, duration_minutes=30)
    db.add(service)
    await db.flush()
    response = await client.post(
        "/api/v1/bookings/",
        json={
            "service_id": str(service.id),
            "scheduled_at": "2099-12-31T10:00:00Z",
            "notes": "Test booking",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "PENDING"
    assert str(data["service_id"]) == str(service.id)


@pytest.mark.asyncio
async def test_get_booking(client: AsyncClient, test_user: User, auth_headers: dict, db: AsyncSession):
    service = Service(name="Get Svc", category="test", price=200, duration_minutes=45)
    db.add(service)
    await db.flush()
    create_resp = await client.post(
        "/api/v1/bookings/",
        json={"service_id": str(service.id), "scheduled_at": "2099-11-01T09:00:00Z"},
        headers=auth_headers,
    )
    booking_id = create_resp.json()["id"]
    response = await client.get(f"/api/v1/bookings/{booking_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["id"] == booking_id


@pytest.mark.asyncio
async def test_list_bookings(client: AsyncClient, test_user: User, auth_headers: dict):
    response = await client.get("/api/v1/bookings/", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_cancel_booking(client: AsyncClient, test_user: User, auth_headers: dict, db: AsyncSession):
    service = Service(name="Cancel Svc", category="test", price=150, duration_minutes=30)
    db.add(service)
    await db.flush()
    create_resp = await client.post(
        "/api/v1/bookings/",
        json={"service_id": str(service.id), "scheduled_at": "2099-10-15T14:00:00Z"},
        headers=auth_headers,
    )
    booking_id = create_resp.json()["id"]
    response = await client.delete(f"/api/v1/bookings/{booking_id}", headers=auth_headers)
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_get_booking_unauthorized(client: AsyncClient, db: AsyncSession):
    service = Service(name="Unauth Svc", category="test", price=100, duration_minutes=20)
    db.add(service)
    await db.flush()
    response = await client.get(f"/api/v1/bookings/{service.id}")
    assert response.status_code == 401
