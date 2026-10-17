"""Roles & permissions API."""

import json

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.core.accounts import get_account_switch, set_account_active
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


@pytest.mark.asyncio
async def test_audit_log_paging_is_bounded(ctx):
    client, _ = ctx
    assert (await client.get("/api/v1/audit-logs", params={"skip": 0, "limit": 200})).status_code == 200
    for params in ({"skip": -1}, {"limit": 0}, {"limit": -5}, {"limit": 201}, {"limit": 10**9}):
        assert (await client.get("/api/v1/audit-logs", params=params)).status_code == 422, params


@pytest.mark.asyncio
async def test_account_switch_keeps_the_user_id_inside_its_path_segment(monkeypatch):
    seen = []

    def handler(request):
        seen.append(request.url.raw_path.decode())
        return httpx.Response(200)

    real_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real_client(**kw, transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", "k")
    await set_account_active("../../admin/x", False)
    assert seen == ["/internal/users/..%2F..%2Fadmin%2Fx/status"]


@pytest.mark.asyncio
async def test_every_audit_entry_records_where_the_admin_acted_from(ctx):
    client, factory = ctx
    origin = {"X-Real-IP": "203.0.113.7", "User-Agent": "AdminDashboard/1.0"}
    assert (
        await client.post("/api/v1/admin/users/victim/ban", json={"reason": "x"}, headers=origin)
    ).status_code == 200
    assert (await client.post("/api/v1/admin/users/victim/unban", headers=origin)).status_code == 200
    bulk = await client.post(
        "/api/v1/admin/actions/bulk-update", json={"user_ids": ["u2"], "action": "ban"}, headers=origin
    )
    assert bulk.status_code == 200
    role = (await client.post("/api/v1/access/roles", json={"name": "ops"}, headers=origin)).json()
    await client.put(f"/api/v1/access/roles/{role['id']}/permissions", json={"permissions": []}, headers=origin)
    await client.delete(f"/api/v1/access/roles/{role['id']}", headers=origin)
    await client.put("/api/v1/system-config/maintenance", json={"value": "on"}, headers=origin)

    async with factory() as db:
        entries = (await db.execute(select(AuditLog))).scalars().all()
    assert sorted(e.action for e in entries) == [
        "ban_user",
        "ban_user",
        "create_role",
        "delete_role",
        "unban_user",
        "update_role_permissions",
        "update_system_config",
    ]
    assert {(e.ip_address, e.user_agent, e.service, e.admin_id) for e in entries} == {
        ("203.0.113.7", "AdminDashboard/1.0", "admin_service", "u1")
    }


@pytest.mark.asyncio
async def test_without_the_gateway_header_the_connecting_address_is_recorded(ctx):
    client, factory = ctx
    await client.post("/api/v1/admin/users/victim/ban", json={"reason": "x"}, headers={"User-Agent": "u" * 2000})
    async with factory() as db:
        entry = (await db.execute(select(AuditLog))).scalar_one()
    assert entry.ip_address == "127.0.0.1"
    assert entry.user_agent == "u" * 512


@pytest.mark.asyncio
async def test_system_config_changes_are_audited_with_the_old_value(ctx):
    client, factory = ctx
    await client.put("/api/v1/system-config/fee_pct", json={"value": "5", "description": "Platform fee"})
    await client.put("/api/v1/system-config/fee_pct", json={"value": "7", "updated_by": "someone-else"})
    async with factory() as db:
        stmt = select(AuditLog).where(AuditLog.action == "update_system_config").order_by(AuditLog.created_at)
        first, second = (await db.execute(stmt)).scalars().all()
    assert (first.resource_type, first.resource_id, first.old_values) == ("system_config", "fee_pct", None)
    assert json.loads(second.old_values) == {"value": "5", "description": "Platform fee"}
    assert json.loads(second.new_values) == {"value": "7", "description": "Platform fee"}
    assert second.admin_id == "u1"


REPORT = {
    "admin_id": "ops",
    "action": "refund_payment",
    "resource_type": "payment",
    "resource_id": "pay-1",
    "old_values": None,
    "new_values": {"amount_cents": 500, "reason": "late"},
    "ip_address": "198.51.100.2",
    "user_agent": "Mozilla/5.0",
    "service": "payment_service",
}
KEY = "k" * 32


@pytest.mark.asyncio
async def test_other_services_record_admin_actions_with_the_internal_key(ctx, monkeypatch):
    client, factory = ctx
    url = "/internal/audit-logs"
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", "")
    assert (await client.post(url, json=REPORT, headers={"X-Internal-Key": ""})).status_code == 503
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", KEY)
    assert (await client.post(url, json=REPORT)).status_code == 401
    assert (await client.post(url, json=REPORT, headers={"X-Internal-Key": "wrong"})).status_code == 401

    key = {"X-Internal-Key": KEY}
    created = await client.post(url, json={**REPORT, "user_agent": "a" * 900}, headers=key)
    assert created.status_code == 201
    assert (created.json()["service"], len(created.json()["user_agent"])) == ("payment_service", 512)
    for bad in ({"service": "Payment Service"}, {"admin_id": ""}, {"action": None}):
        assert (await client.post(url, json={**REPORT, **bad}, headers=key)).status_code == 422, bad

    async with factory() as db:
        entry = (await db.execute(select(AuditLog))).scalar_one()
    assert (entry.admin_id, entry.resource_id, entry.ip_address) == ("ops", "pay-1", "198.51.100.2")
    assert entry.old_values is None
    assert json.loads(entry.new_values) == {"amount_cents": 500, "reason": "late"}


@pytest.mark.asyncio
async def test_the_viewer_shows_which_service_recorded_each_entry(ctx, monkeypatch):
    client, _ = ctx
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", KEY)
    await client.post("/internal/audit-logs", json=REPORT, headers={"X-Internal-Key": KEY})
    await client.post("/api/v1/admin/users/victim/ban", json={"reason": "x"}, headers={"User-Agent": "Dash"})

    every = (await client.get("/api/v1/audit-logs")).json()
    assert {(e["service"], e["user_agent"]) for e in every} == {
        ("payment_service", "Mozilla/5.0"),
        ("admin_service", "Dash"),
    }
    only = (await client.get("/api/v1/audit-logs", params={"service": "payment_service"})).json()
    assert [e["action"] for e in only] == ["refund_payment"]
