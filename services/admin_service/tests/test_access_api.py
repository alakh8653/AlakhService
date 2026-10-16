"""Roles & permissions API."""

import json

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.core.accounts import get_account_switch
from app.core.permissions import DEFAULT_ROLES, PERMISSIONS
from app.database import Base, get_db
from app.main import app
from app.models.admin import AdminUser, AuditLog, Role

SWITCHED: list = []
KNOWN_USERS = {"victim", "u2", "u3"}


async def fake_switch(user_id: str, active: bool) -> None:
    """Stands in for auth_service's account switch."""
    from fastapi import HTTPException

    if user_id not in KNOWN_USERS:
        raise HTTPException(status_code=404, detail="User not found")
    SWITCHED.append((user_id, active))


def auth(sub: str, role: str = "admin") -> dict:
    token = jwt.encode({"sub": sub, "role": role, "type": "access"}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def ctx():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        for name, (desc, perms) in DEFAULT_ROLES.items():
            db.add(Role(id=f"role-{name}", name=name, description=desc, permissions=json.dumps(perms), is_system=True))
        db.add_all(
            [
                AdminUser(id="a1", user_id="u1", role="admin"),
                AdminUser(id="a2", user_id="u2", role="support"),
                AdminUser(id="a3", user_id="u3", role="support"),
                AdminUser(id="a4", user_id="u4", role="support", is_active=False),
            ]
        )
        await db.commit()

    async def override_get_db():
        async with factory() as session:
            yield session
            await session.commit()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_account_switch] = lambda: fake_switch
    SWITCHED.clear()
    # Requests are made as admin u1 unless a test says otherwise.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers=auth("u1")) as client:
        yield client, factory
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_permission_catalogue(ctx):
    client, _ = ctx
    perms = (await client.get("/api/v1/access/permissions")).json()
    assert {p["key"] for p in perms} == set(PERMISSIONS)
    assert all(p["resource"] and p["description"] for p in perms)


@pytest.mark.asyncio
async def test_roles_list_with_active_user_counts(ctx):
    client, _ = ctx
    roles = {r["name"]: r for r in (await client.get("/api/v1/access/roles")).json()}
    assert set(roles) == set(DEFAULT_ROLES)
    assert roles["admin"]["user_count"] == 1
    assert roles["support"]["user_count"] == 2  # inactive admin users are not counted
    assert roles["viewer"]["user_count"] == 0
    assert roles["admin"]["permissions"] == sorted(PERMISSIONS)


@pytest.mark.asyncio
async def test_create_role_validates_and_rejects_duplicates(ctx):
    client, _ = ctx
    created = await client.post(
        "/api/v1/access/roles",
        json={"name": "auditor", "description": "Audit only", "permissions": ["audit:read", "audit:read"]},
    )
    assert created.status_code == 201
    assert created.json()["permissions"] == ["audit:read"]
    assert created.json()["is_system"] is False

    assert (await client.post("/api/v1/access/roles", json={"name": "auditor"})).status_code == 409
    assert (await client.post("/api/v1/access/roles", json={"name": "x2", "permissions": ["nope"]})).status_code == 422
    assert (await client.post("/api/v1/access/roles", json={"name": "Bad Name"})).status_code == 422


@pytest.mark.asyncio
async def test_update_permissions_is_audited_and_admin_is_protected(ctx):
    client, factory = ctx
    resp = await client.put(
        "/api/v1/access/roles/role-support/permissions",
        json={"permissions": ["disputes:read"]},
    )
    assert resp.status_code == 200
    assert resp.json()["permissions"] == ["disputes:read"]

    async with factory() as db:
        entry = (await db.execute(select(AuditLog).where(AuditLog.action == "update_role_permissions"))).scalar_one()
    assert entry.admin_id == "u1"
    assert entry.resource_id == "role-support"
    assert json.loads(entry.new_values) == ["disputes:read"]
    assert "users:ban" in json.loads(entry.old_values)

    admin = await client.put("/api/v1/access/roles/role-admin/permissions", json={"permissions": []})
    assert admin.status_code == 409
    assert (await client.put("/api/v1/access/roles/missing/permissions", json={"permissions": []})).status_code == 404


@pytest.mark.asyncio
async def test_delete_role_rules(ctx):
    client, factory = ctx
    assert (await client.delete("/api/v1/access/roles/role-viewer")).status_code == 409  # built-in

    custom = (await client.post("/api/v1/access/roles", json={"name": "temp"})).json()
    assert (await client.delete(f"/api/v1/access/roles/{custom['id']}")).status_code == 204
    names = {r["name"] for r in (await client.get("/api/v1/access/roles")).json()}
    assert "temp" not in names

    ops = (await client.post("/api/v1/access/roles", json={"name": "ops"})).json()
    async with factory() as db:
        db.add(AdminUser(id="a5", user_id="u5", role="ops"))
        await db.commit()
    in_use = await client.delete(f"/api/v1/access/roles/{ops['id']}")
    assert in_use.status_code == 409
    assert "assigned to 1" in in_use.json()["detail"]


@pytest.mark.asyncio
async def test_only_admin_tokens_are_accepted(ctx):
    client, factory = ctx
    url = "/api/v1/access/roles"
    assert (await client.get(url, headers={"Authorization": ""})).status_code == 401
    assert (await client.get(url, headers=auth("u2", role="user"))).status_code == 403
    refresh = jwt.encode(
        {"sub": "u1", "role": "admin", "type": "refresh"}, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    assert (await client.get(url, headers={"Authorization": f"Bearer {refresh}"})).status_code == 401
    assert (await client.get("/api/v1/audit-logs", headers=auth("u2", role="user"))).status_code == 403


@pytest.mark.asyncio
async def test_audit_entries_name_the_admin_from_the_token(ctx):
    client, factory = ctx
    resp = await client.post(
        "/api/v1/admin/users/victim/ban",
        json={"reason": "spam", "banned_by": "someone-else"},
        headers={**auth("u1"), "x-user-id": "someone-else"},
    )
    assert resp.status_code == 200
    async with factory() as db:
        entry = (await db.execute(select(AuditLog).where(AuditLog.action == "ban_user"))).scalar_one()
    assert entry.admin_id == "u1"


@pytest.mark.asyncio
async def test_bans_are_enforced_by_auth_service_before_they_are_recorded(ctx):
    client, factory = ctx
    assert (await client.post("/api/v1/admin/users/victim/ban", json={"reason": "fraud"})).status_code == 200
    assert SWITCHED == [("victim", False)]

    # An account auth_service doesn't know is not "banned" here either.
    assert (await client.post("/api/v1/admin/users/ghost/ban", json={"reason": "x"})).status_code == 404
    async with factory() as db:
        from app.models.admin import BannedUser

        banned = (await db.execute(select(BannedUser.user_id).where(BannedUser.is_active == True))).scalars().all()  # noqa: E712
    assert banned == ["victim"]

    assert (await client.post("/api/v1/admin/users/u1/ban", json={"reason": "oops"})).status_code == 400
    assert (await client.post("/api/v1/admin/users/victim/unban")).status_code == 200
    assert SWITCHED[-1] == ("victim", True)
    # Banning again after an unban reuses the record rather than colliding with it.
    assert (await client.post("/api/v1/admin/users/victim/ban", json={"reason": "again"})).status_code == 200
    async with factory() as db:
        from app.models.admin import BannedUser

        again = (await db.execute(select(BannedUser).where(BannedUser.user_id == "victim"))).scalars().all()
    assert [(b.is_active, b.reason) for b in again] == [(True, "again")]

    bulk = await client.post(
        "/api/v1/admin/actions/bulk-update", json={"user_ids": ["u2", "ghost", "u1"], "action": "ban", "admin_id": "x"}
    )
    statuses = {r["user_id"]: r["status"] for r in bulk.json()["results"]}
    assert statuses == {"u2": "banned", "ghost": "failed", "u1": "failed"}
