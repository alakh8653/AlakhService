from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.accounts import AccountSwitch, get_account_switch
from app.database import get_db
from app.dependencies import Caller, require_admin
from app.schemas.admin import (
    AdminUserCreate,
    AdminUserResponse,
    AuditLogResponse,
    BanUserRequest,
    BulkUpdateRequest,
    SystemConfigResponse,
    SystemConfigUpdate,
)
from app.services.admin_service import admin_service

router = APIRouter()


@router.post("/admin/users", response_model=AdminUserResponse, status_code=201)
async def create_admin_user(data: AdminUserCreate, db: AsyncSession = Depends(get_db)):
    return await admin_service.create_admin_user(db, data)


@router.get("/admin/users", response_model=List[AdminUserResponse])
async def list_admin_users(db: AsyncSession = Depends(get_db)):
    return await admin_service.list_admin_users(db)


@router.post("/admin/users/{user_id}/ban", status_code=200)
async def ban_user(
    user_id: str,
    data: BanUserRequest,
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(require_admin),
    switch: AccountSwitch = Depends(get_account_switch),
):
    """Records the ban, then deactivates the account in auth_service (no sign-in, sessions ended).

    If auth_service cannot make the change the request fails and the record is rolled back.
    """
    if user_id == caller.user_id:
        raise HTTPException(status_code=400, detail="You cannot ban yourself")
    # Audit entries name the admin from the token, never one the client supplies.
    data = data.model_copy(update={"banned_by": caller.user_id})
    result = await admin_service.ban_user(db, user_id, data)
    await switch(user_id, False)
    return result


@router.post("/admin/users/{user_id}/unban", status_code=200)
async def unban_user(
    user_id: str,
    admin_id: Optional[str] = Query(None, description="Ignored; the acting admin comes from the token"),
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(require_admin),
    switch: AccountSwitch = Depends(get_account_switch),
):
    result = await admin_service.unban_user(db, user_id, caller.user_id)
    await switch(user_id, True)
    return result


@router.get("/audit-logs", response_model=List[AuditLogResponse])
async def get_audit_logs(
    admin_id: Optional[str] = None,
    action: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.get_audit_logs(db, admin_id=admin_id, action=action, skip=skip, limit=limit)


@router.get("/system-config", response_model=List[SystemConfigResponse])
async def get_system_configs(db: AsyncSession = Depends(get_db)):
    return await admin_service.get_system_configs(db)


@router.put("/system-config/{key}", response_model=SystemConfigResponse)
async def update_system_config(
    key: str, data: SystemConfigUpdate, db: AsyncSession = Depends(get_db), caller: Caller = Depends(require_admin)
):
    data = data.model_copy(update={"updated_by": caller.user_id})
    return await admin_service.update_system_config(db, key, data)


@router.post("/admin/actions/bulk-update")
async def bulk_update(
    data: BulkUpdateRequest,
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(require_admin),
    switch: AccountSwitch = Depends(get_account_switch),
):
    """Bans or unbans several accounts; only those auth_service actually switched are recorded."""
    failed = []
    if data.action in ("ban", "unban"):
        applied = []
        for user_id in data.user_ids:
            if data.action == "ban" and user_id == caller.user_id:
                failed.append({"status": "failed", "user_id": user_id, "detail": "You cannot ban yourself"})
                continue
            try:
                await switch(user_id, data.action == "unban")
                applied.append(user_id)
            except HTTPException as e:
                failed.append({"status": "failed", "user_id": user_id, "detail": e.detail})
        data = data.model_copy(update={"user_ids": applied})
    data = data.model_copy(update={"admin_id": caller.user_id})
    result = await admin_service.bulk_update(db, data)
    return {"processed": result["processed"], "results": result["results"] + failed}
