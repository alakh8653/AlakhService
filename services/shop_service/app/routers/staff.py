from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ShopNotFoundError, StaffNotFoundError
from app.database import get_db
from app.dependencies import Caller, ensure_owner, require_caller
from app.schemas.shop import StaffCreate, StaffResponse, StaffUpdate
from app.services import staff_service
from app.services.shop_service import shop_service

router = APIRouter()


async def _owned_shop(db: AsyncSession, shop_id: str, caller: Caller):
    try:
        shop = await shop_service.get_shop(db, shop_id)
    except ShopNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    ensure_owner(shop.owner_id, caller)
    return shop


async def _owned_member(db: AsyncSession, staff_id: str, caller: Caller):
    try:
        member = await staff_service.get_staff(db, staff_id)
    except StaffNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    await _owned_shop(db, member.shop_id, caller)
    return member


@router.get("/staff", response_model=List[StaffResponse])
async def list_staff(
    shop_id: str = Query(...),
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(require_caller),
):
    await _owned_shop(db, shop_id, caller)
    return [staff_service.to_response(m) for m in await staff_service.list_staff(db, shop_id, include_inactive)]


@router.post("/staff", response_model=StaffResponse, status_code=201)
async def create_staff(data: StaffCreate, db: AsyncSession = Depends(get_db), caller: Caller = Depends(require_caller)):
    await _owned_shop(db, data.shop_id, caller)
    return staff_service.to_response(await staff_service.create_staff(db, data))


@router.put("/staff/{staff_id}", response_model=StaffResponse)
async def update_staff(
    staff_id: str, data: StaffUpdate, db: AsyncSession = Depends(get_db), caller: Caller = Depends(require_caller)
):
    member = await _owned_member(db, staff_id, caller)
    return staff_service.to_response(await staff_service.update_staff(db, member, data))


@router.delete("/staff/{staff_id}", status_code=204)
async def delete_staff(staff_id: str, db: AsyncSession = Depends(get_db), caller: Caller = Depends(require_caller)):
    member = await _owned_member(db, staff_id, caller)
    await db.delete(member)
    await db.flush()
    return Response(status_code=204)
