from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import RoleConflictError, RoleNotFoundError
from app.database import get_db
from app.dependencies import Caller, require_admin
from app.schemas.access import PermissionResponse, RoleCreate, RolePermissionsUpdate, RoleResponse
from app.services import access_service

router = APIRouter()

ActorId = Optional[str]


def actor(caller: Caller = Depends(require_admin)) -> ActorId:
    """The admin making the change, from the access token; used to attribute audit log entries."""
    return caller.user_id


@router.get("/access/permissions", response_model=List[PermissionResponse])
async def list_permissions():
    return access_service.list_permissions()


@router.get("/access/roles", response_model=List[RoleResponse])
async def list_roles(db: AsyncSession = Depends(get_db)):
    return await access_service.list_roles(db)


@router.post("/access/roles", response_model=RoleResponse, status_code=201)
async def create_role(data: RoleCreate, db: AsyncSession = Depends(get_db), actor_id: ActorId = Depends(actor)):
    try:
        return await access_service.create_role(db, data, actor_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except RoleConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.put("/access/roles/{role_id}/permissions", response_model=RoleResponse)
async def update_role_permissions(
    role_id: str, data: RolePermissionsUpdate, db: AsyncSession = Depends(get_db), actor_id: ActorId = Depends(actor)
):
    try:
        return await access_service.update_permissions(db, role_id, data.permissions, actor_id)
    except RoleNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except RoleConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.delete("/access/roles/{role_id}", status_code=204)
async def delete_role(role_id: str, db: AsyncSession = Depends(get_db), actor_id: ActorId = Depends(actor)):
    try:
        await access_service.delete_role(db, role_id, actor_id)
    except RoleNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except RoleConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return Response(status_code=204)
