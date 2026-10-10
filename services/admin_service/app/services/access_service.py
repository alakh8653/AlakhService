"""Roles and permissions for admin users, with every change written to the audit log."""
import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import RoleConflictError, RoleNotFoundError
from app.core.permissions import PERMISSIONS, PROTECTED_ROLES
from app.models.admin import AdminUser, AuditLog, Role
from app.schemas.access import PermissionResponse, RoleCreate, RoleResponse


def list_permissions() -> List[PermissionResponse]:
    return [PermissionResponse(key=k, resource=r, description=d) for k, (r, d) in PERMISSIONS.items()]


def _validate(permissions: List[str]) -> List[str]:
    unknown = sorted(set(permissions) - set(PERMISSIONS))
    if unknown:
        raise ValueError(f"Unknown permissions: {', '.join(unknown)}")
    return sorted(set(permissions))


async def _user_counts(db: AsyncSession) -> dict:
    rows = await db.execute(
        select(AdminUser.role, func.count()).where(AdminUser.is_active == True).group_by(AdminUser.role)  # noqa: E712
    )
    return dict(rows.all())


def _to_response(role: Role, counts: dict) -> RoleResponse:
    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        permissions=json.loads(role.permissions or "[]"),
        is_system=role.is_system,
        user_count=counts.get(role.name, 0),
        created_at=role.created_at,
    )


async def _audit(db: AsyncSession, actor: Optional[str], action: str, role: Role, old, new) -> None:
    db.add(
        AuditLog(
            id=str(uuid.uuid4()),
            admin_id=actor or "unknown",
            action=action,
            resource_type="role",
            resource_id=role.id,
            old_values=json.dumps(old) if old is not None else None,
            new_values=json.dumps(new) if new is not None else None,
            created_at=datetime.now(timezone.utc),
        )
    )


async def _get(db: AsyncSession, role_id: str) -> Role:
    role = (await db.execute(select(Role).where(Role.id == role_id))).scalar_one_or_none()
    if role is None:
        raise RoleNotFoundError()
    return role


async def list_roles(db: AsyncSession) -> List[RoleResponse]:
    roles = (await db.execute(select(Role).order_by(Role.is_system.desc(), Role.name))).scalars().all()
    counts = await _user_counts(db)
    return [_to_response(r, counts) for r in roles]


async def create_role(db: AsyncSession, data: RoleCreate, actor: Optional[str]) -> RoleResponse:
    if (await db.execute(select(Role).where(Role.name == data.name))).scalar_one_or_none():
        raise RoleConflictError(f"Role '{data.name}' already exists")
    role = Role(
        id=str(uuid.uuid4()),
        name=data.name,
        description=data.description,
        permissions=json.dumps(_validate(data.permissions)),
        is_system=False,
        created_at=datetime.now(timezone.utc),
    )
    db.add(role)
    await _audit(db, actor, "create_role", role, None, {"name": role.name, "permissions": json.loads(role.permissions)})
    await db.flush()
    return _to_response(role, await _user_counts(db))


async def update_permissions(db: AsyncSession, role_id: str, permissions: List[str], actor: Optional[str]) -> RoleResponse:
    role = await _get(db, role_id)
    if role.name in PROTECTED_ROLES:
        raise RoleConflictError(f"The '{role.name}' role always has every permission")
    old = json.loads(role.permissions or "[]")
    new = _validate(permissions)
    role.permissions = json.dumps(new)
    await _audit(db, actor, "update_role_permissions", role, old, new)
    await db.flush()
    return _to_response(role, await _user_counts(db))


async def delete_role(db: AsyncSession, role_id: str, actor: Optional[str]) -> None:
    role = await _get(db, role_id)
    if role.is_system:
        raise RoleConflictError(f"Built-in role '{role.name}' cannot be deleted")
    in_use = (await _user_counts(db)).get(role.name, 0)
    if in_use:
        raise RoleConflictError(f"Role '{role.name}' is assigned to {in_use} admin user(s)")
    await _audit(db, actor, "delete_role", role, {"name": role.name, "permissions": json.loads(role.permissions)}, None)
    await db.delete(role)
    await db.flush()
