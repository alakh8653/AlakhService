from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.database import get_db
from app.schemas.admin import AdminUserCreate, AdminUserResponse, AuditLogResponse, SystemConfigUpdate, SystemConfigResponse, BanUserRequest, BulkUpdateRequest
from app.services.admin_service import admin_service
from app.core.exceptions import AdminUserNotFoundError

router = APIRouter()


@router.post("/admin/users", response_model=AdminUserResponse, status_code=201)
async def create_admin_user(data: AdminUserCreate, db: AsyncSession = Depends(get_db)):
    return await admin_service.create_admin_user(db, data)


@router.get("/admin/users", response_model=List[AdminUserResponse])
async def list_admin_users(db: AsyncSession = Depends(get_db)):
    return await admin_service.list_admin_users(db)


@router.post("/admin/users/{user_id}/ban", status_code=200)
async def ban_user(user_id: str, data: BanUserRequest, db: AsyncSession = Depends(get_db)):
    return await admin_service.ban_user(db, user_id, data)


@router.post("/admin/users/{user_id}/unban", status_code=200)
async def unban_user(user_id: str, admin_id: str = Query(...), db: AsyncSession = Depends(get_db)):
    return await admin_service.unban_user(db, user_id, admin_id)


@router.get("/audit-logs", response_model=List[AuditLogResponse])
async def get_audit_logs(
    admin_id: Optional[str] = None,
    action: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.get_audit_logs(db, admin_id=admin_id, action=action, skip=skip, limit=limit)


@router.get("/system-config", response_model=List[SystemConfigResponse])
async def get_system_configs(db: AsyncSession = Depends(get_db)):
    return await admin_service.get_system_configs(db)


@router.put("/system-config/{key}", response_model=SystemConfigResponse)
async def update_system_config(key: str, data: SystemConfigUpdate, db: AsyncSession = Depends(get_db)):
    return await admin_service.update_system_config(db, key, data)


@router.post("/admin/actions/bulk-update")
async def bulk_update(data: BulkUpdateRequest, db: AsyncSession = Depends(get_db)):
    return await admin_service.bulk_update(db, data)
