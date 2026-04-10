import uuid
import json
from datetime import datetime, timezone
from typing import List, Optional
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.admin import AdminUser, AuditLog, SystemConfig, BannedUser
from app.schemas.admin import AdminUserCreate, SystemConfigUpdate, BanUserRequest, BulkUpdateRequest

log = structlog.get_logger()


class AdminService:

    async def create_admin_user(self, db: AsyncSession, data: AdminUserCreate) -> AdminUser:
        admin = AdminUser(
            id=str(uuid.uuid4()),
            user_id=data.user_id,
            role=data.role,
            permissions=json.dumps(data.permissions) if data.permissions else None,
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        db.add(admin)
        await db.flush()
        log.info("admin_user_created", user_id=data.user_id, role=data.role)
        return admin

    async def list_admin_users(self, db: AsyncSession) -> List[AdminUser]:
        result = await db.execute(select(AdminUser).where(AdminUser.is_active == True))
        return list(result.scalars().all())

    async def ban_user(self, db: AsyncSession, user_id: str, data: BanUserRequest) -> dict:
        # Check if already banned
        result = await db.execute(select(BannedUser).where(BannedUser.user_id == user_id, BannedUser.is_active == True))
        existing = result.scalar_one_or_none()
        if not existing:
            banned = BannedUser(
                id=str(uuid.uuid4()),
                user_id=user_id,
                reason=data.reason,
                banned_by=data.banned_by,
                banned_at=datetime.now(timezone.utc),
                is_active=True,
            )
            db.add(banned)

        await self._log_audit(db, data.banned_by, "ban_user", "user", user_id, new_values=json.dumps({"reason": data.reason}))
        await db.flush()
        log.info("user_banned", user_id=user_id, banned_by=data.banned_by)
        return {"status": "banned", "user_id": user_id}

    async def unban_user(self, db: AsyncSession, user_id: str, admin_id: str) -> dict:
        result = await db.execute(select(BannedUser).where(BannedUser.user_id == user_id, BannedUser.is_active == True))
        banned = result.scalar_one_or_none()
        if banned:
            banned.is_active = False
        await self._log_audit(db, admin_id, "unban_user", "user", user_id)
        await db.flush()
        log.info("user_unbanned", user_id=user_id, admin_id=admin_id)
        return {"status": "unbanned", "user_id": user_id}

    async def get_audit_logs(self, db: AsyncSession, admin_id: Optional[str] = None, action: Optional[str] = None, skip: int = 0, limit: int = 50) -> List[AuditLog]:
        stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)
        if admin_id:
            stmt = stmt.where(AuditLog.admin_id == admin_id)
        if action:
            stmt = stmt.where(AuditLog.action == action)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_system_configs(self, db: AsyncSession) -> List[SystemConfig]:
        result = await db.execute(select(SystemConfig))
        return list(result.scalars().all())

    async def update_system_config(self, db: AsyncSession, key: str, data: SystemConfigUpdate) -> SystemConfig:
        result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
        config = result.scalar_one_or_none()
        if not config:
            config = SystemConfig(
                id=str(uuid.uuid4()),
                key=key,
                value=data.value,
                description=data.description,
                updated_by=data.updated_by,
                updated_at=datetime.now(timezone.utc),
            )
            db.add(config)
        else:
            config.value = data.value
            if data.description:
                config.description = data.description
            config.updated_by = data.updated_by
            config.updated_at = datetime.now(timezone.utc)
        await db.flush()
        log.info("system_config_updated", key=key, updated_by=data.updated_by)
        return config

    async def bulk_update(self, db: AsyncSession, data: BulkUpdateRequest) -> dict:
        results = []
        for user_id in data.user_ids:
            if data.action == "ban":
                result = await self.ban_user(db, user_id, BanUserRequest(reason=data.reason, banned_by=data.admin_id))
            elif data.action == "unban":
                result = await self.unban_user(db, user_id, data.admin_id)
            else:
                result = {"status": "unknown_action", "user_id": user_id}
            results.append(result)
        return {"processed": len(results), "results": results}

    async def _log_audit(self, db: AsyncSession, admin_id: str, action: str, resource_type: str, resource_id: Optional[str] = None, old_values: Optional[str] = None, new_values: Optional[str] = None, ip_address: Optional[str] = None) -> AuditLog:
        log_entry = AuditLog(
            id=str(uuid.uuid4()),
            admin_id=admin_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            old_values=old_values,
            new_values=new_values,
            ip_address=ip_address,
            created_at=datetime.now(timezone.utc),
        )
        db.add(log_entry)
        return log_entry


admin_service = AdminService()
