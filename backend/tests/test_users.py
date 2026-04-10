import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.core.security import get_password_hash, create_access_token


@pytest.mark.asyncio
async def test_get_me(client: AsyncClient, test_user: User, auth_headers: dict):
    response = await client.get("/api/v1/users/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["email"] == test_user.email


@pytest.mark.asyncio
async def test_update_me(client: AsyncClient, test_user: User, auth_headers: dict):
    response = await client.put(
        "/api/v1/users/me",
        json={"full_name": "Updated Name"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "Updated Name"


@pytest.mark.asyncio
async def test_get_me_unauthorized(client: AsyncClient):
    response = await client.get("/api/v1/users/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_users_as_admin(client: AsyncClient, db: AsyncSession, test_user: User):
    admin = User(
        email="admin@example.com",
        hashed_password=get_password_hash("AdminPass123"),
        full_name="Admin User",
        is_active=True,
        is_superuser=True,
    )
    db.add(admin)
    await db.flush()
    token = create_access_token(data={"sub": admin.email})
    response = await client.get(
        "/api/v1/users/", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_list_users_as_regular_user_forbidden(
    client: AsyncClient, test_user: User, auth_headers: dict
):
    response = await client.get("/api/v1/users/", headers=auth_headers)
    assert response.status_code == 403
