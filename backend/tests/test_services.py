import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.service import Service
from app.core.security import get_password_hash, create_access_token


async def _admin_headers(db: AsyncSession) -> dict:
    admin = User(
        email="svc_admin@example.com",
        hashed_password=get_password_hash("AdminPass123"),
        is_active=True,
        is_superuser=True,
    )
    db.add(admin)
    await db.flush()
    token = create_access_token(data={"sub": admin.email})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_list_services(client: AsyncClient, db: AsyncSession):
    service = Service(name="Haircut", category="beauty", price=200, duration_minutes=30)
    db.add(service)
    await db.flush()
    response = await client.get("/api/v1/services/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_get_service(client: AsyncClient, db: AsyncSession):
    service = Service(name="Massage", category="wellness", price=500, duration_minutes=60)
    db.add(service)
    await db.flush()
    response = await client.get(f"/api/v1/services/{service.id}")
    assert response.status_code == 200
    assert response.json()["name"] == "Massage"


@pytest.mark.asyncio
async def test_create_service_as_admin(client: AsyncClient, db: AsyncSession):
    headers = await _admin_headers(db)
    response = await client.post(
        "/api/v1/services/",
        json={"name": "Facial", "category": "beauty", "price": "350.00", "duration_minutes": 45},
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["name"] == "Facial"


@pytest.mark.asyncio
async def test_create_service_as_user_forbidden(
    client: AsyncClient, auth_headers: dict
):
    response = await client.post(
        "/api/v1/services/",
        json={"name": "Nails", "category": "beauty", "price": "150.00", "duration_minutes": 30},
        headers=auth_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_service(client: AsyncClient, db: AsyncSession):
    headers = await _admin_headers(db)
    service = Service(name="Old Service", category="other", price=100, duration_minutes=20)
    db.add(service)
    await db.flush()
    response = await client.put(
        f"/api/v1/services/{service.id}",
        json={"name": "Updated Service"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Service"
