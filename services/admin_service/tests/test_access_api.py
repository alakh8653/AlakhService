"""Roles & permissions API."""
import json

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.permissions import DEFAULT_ROLES, PERMISSIONS
from app.database import Base, get_db
from app.main import app
from app.models.admin import AdminUser, AuditLog, Role


@pytest_asyncio.fixture
async def ctx():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        for name, (desc, perms) in DEFAULT_ROLES.items():
            db.add(Role(id=f"role-{name}", name=name, description=desc, permissions=json.dumps(perms), is_system=True))
        db.add_all([
            AdminUser(id="a1", user_id="u1", role="admin"),
            AdminUser(id="a2", user_id="u2", role="support"),
            AdminUser(id="a3", user_id="u3", role="support"),
            AdminUser(id="a4", user_id="u4", role="support", is_active=False),
        ])
        await db.commit()

    async def override_get_db():
        async with factory() as session:
            yield session
            await session.commit()

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
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
        "/api/v1/access/roles", json={"name": "auditor", "description": "Audit only", "permissions": ["audit:read", "audit:read"]}
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
        headers={"x-user-id": "u1"},
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
