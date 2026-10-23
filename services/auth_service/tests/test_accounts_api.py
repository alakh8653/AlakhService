"""Admins look up accounts; a ban (from admin_service) stops sign-in and ends existing sessions."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.core.security import create_access_token
from app.database import Base, get_db
from app.dependencies import get_redis
from app.main import app

KEY = "internal-test-key"


class FakeRedis:
    def __init__(self):
        self.store = {}

    async def get(self, key):
        return self.store.get(key)

    async def incr(self, key):
        self.store[key] = int(self.store.get(key, 0)) + 1
        return self.store[key]

    async def expire(self, key, ttl):
        return True

    async def delete(self, key):
        self.store.pop(key, None)

    async def ttl(self, key):
        return -1

    async def setex(self, key, ttl, value):
        self.store[key] = value


def bearer(sub: str, role: str = "user") -> dict:
    return {"Authorization": f"Bearer {create_access_token({'sub': sub, 'role': role})}"}


@pytest_asyncio.fixture
async def client(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", KEY)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    redis = FakeRedis()

    async def override_get_db():
        async with factory() as session:
            yield session
            await session.commit()

    async def override_redis():
        yield redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_redis
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        for email, name in (("ravi@example.com", "Ravi Kumar"), ("asha@example.com", "Asha Rao")):
            assert (
                await ac.post(
                    "/api/v1/auth/register",
                    json={
                        "email": email,
                        "password": "Passw0rd!",
                        "full_name": name,
                        "accepted_terms_version": "2026-10",
                    },
                )
            ).status_code == 201
        yield ac
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_only_admins_search_accounts(client):
    assert (await client.get("/api/v1/auth/users")).status_code in (401, 403)
    assert (await client.get("/api/v1/auth/users", headers=bearer("u1"))).status_code == 403

    found = await client.get("/api/v1/auth/users", params={"q": "ravi"}, headers=bearer("ops", "admin"))
    assert [u["email"] for u in found.json()] == ["ravi@example.com"]
    assert "hashed_password" not in found.json()[0]
    everyone = await client.get("/api/v1/auth/users", headers=bearer("ops", "admin"))
    assert len(everyone.json()) == 2


@pytest.mark.asyncio
async def test_a_banned_account_cannot_sign_in_or_keep_its_session(client):
    session = (
        await client.post("/api/v1/auth/login", json={"email": "ravi@example.com", "password": "Passw0rd!"})
    ).json()
    ravi = (await client.get("/api/v1/auth/users", params={"q": "ravi"}, headers=bearer("ops", "admin"))).json()[0]
    url = f"/internal/users/{ravi['id']}/status"

    banned = await client.post(url, json={"is_active": False}, headers={"X-Internal-Key": KEY})
    assert (banned.status_code, banned.json()["is_active"]) == (200, False)

    login = await client.post("/api/v1/auth/login", json={"email": "ravi@example.com", "password": "Passw0rd!"})
    assert (login.status_code, login.json()["detail"]) == (401, "Account is disabled")
    assert (
        await client.post("/api/v1/auth/refresh", json={"refresh_token": session["refresh_token"]})
    ).status_code == 401

    assert (await client.post(url, json={"is_active": True}, headers={"X-Internal-Key": KEY})).json()[
        "is_active"
    ] is True
    assert (
        await client.post("/api/v1/auth/login", json={"email": "ravi@example.com", "password": "Passw0rd!"})
    ).status_code == 200


@pytest.mark.asyncio
async def test_only_services_holding_the_key_switch_accounts(client, monkeypatch):
    url = "/internal/users/whoever/status"
    assert (await client.post(url, json={"is_active": False})).status_code == 401
    assert (await client.post(url, json={"is_active": False}, headers=bearer("ops", "admin"))).status_code == 401
    assert (await client.post(url, json={"is_active": False}, headers={"X-Internal-Key": KEY})).status_code == 404
    assert (
        await client.post("/api/v1" + url, json={"is_active": False}, headers={"X-Internal-Key": KEY})
    ).status_code == 404
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", "")
    assert (await client.post(url, json={"is_active": False}, headers={"X-Internal-Key": ""})).status_code == 503


@pytest.mark.asyncio
async def test_operators_grant_admin_from_the_command_line():
    from app.cli import set_role
    from app.schemas.auth import UserCreate
    from app.services.auth_service import AuthService

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)() as db:
        await AuthService().register(db, UserCreate(email="ops@example.com", password="Passw0rd!", full_name="Ops"))
        assert (await set_role(db, "OPS@example.com", "admin")).role == "admin"
        with pytest.raises(LookupError):
            await set_role(db, "nobody@example.com", "admin")
    await engine.dispose()


@pytest.mark.asyncio
async def test_people_can_delete_their_own_account(client):
    from app.routers.users import get_profile_eraser

    erased, failing = [], []

    async def fake_erase(token):
        if failing:
            from fastapi import HTTPException

            raise HTTPException(status_code=503, detail="Could not delete your account right now. Please try again.")
        erased.append(token)

    app.dependency_overrides[get_profile_eraser] = lambda: fake_erase
    session = (
        await client.post("/api/v1/auth/login", json={"email": "ravi@example.com", "password": "Passw0rd!"})
    ).json()
    me = {"Authorization": f"Bearer {session['access_token']}"}

    assert (await client.post("/api/v1/auth/delete-account", json={"password": "wrong"}, headers=me)).status_code == 401
    failing.append(True)
    assert (
        await client.post("/api/v1/auth/delete-account", json={"password": "Passw0rd!"}, headers=me)
    ).status_code == 503
    # Nothing changed while the profile couldn't be erased.
    assert (
        await client.post("/api/v1/auth/login", json={"email": "ravi@example.com", "password": "Passw0rd!"})
    ).status_code == 200
    failing.clear()

    deleted = await client.post("/api/v1/auth/delete-account", json={"password": "Passw0rd!"}, headers=me)
    assert deleted.status_code == 200
    assert erased == [session["access_token"]]
    assert (
        await client.post("/api/v1/auth/login", json={"email": "ravi@example.com", "password": "Passw0rd!"})
    ).status_code == 401
    assert (
        await client.post("/api/v1/auth/refresh", json={"refresh_token": session["refresh_token"]})
    ).status_code == 401
    # The email is free again for a new account.
    again = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "ravi@example.com",
            "password": "Passw0rd!",
            "full_name": "New Ravi",
            "accepted_terms_version": "2026-10",
        },
    )
    assert again.status_code == 201
