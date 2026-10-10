from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import EntryNotFoundError, QueueFullError, QueueNotFoundError
from app.database import get_db
from app.dependencies import (
    Caller,
    OwnerLookup,
    ensure_self_or_admin,
    get_service_owner_lookup,
    require_caller,
)
from app.models.queue import QueueEntry
from app.schemas.queue import QueueCreate, QueueEntryResponse, QueueJoinRequest, QueuePositionResponse, QueueResponse
from app.services.queue_service import queue_service

router = APIRouter()


@router.post("/queues", response_model=QueueResponse, status_code=201)
async def create_queue(
    data: QueueCreate,
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(require_caller),
    lookup_owner: OwnerLookup = Depends(get_service_owner_lookup),
):
    # A queue belongs to a service; only the owner of the shop offering it (or an admin) opens one.
    if not caller.is_admin:
        owner = await lookup_owner(data.service_id)
        if owner is None:
            raise HTTPException(status_code=404, detail="Service not found")
        if owner != caller.user_id:
            raise HTTPException(status_code=403, detail="Not your shop")
    return await queue_service.create_queue(db, data)


@router.get("/queues/{queue_id}", response_model=QueueResponse)
async def get_queue(queue_id: str, db: AsyncSession = Depends(get_db), caller: Caller = Depends(require_caller)):
    try:
        return await queue_service.get_queue(db, queue_id)
    except QueueNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/queues/{queue_id}/join", response_model=QueueEntryResponse, status_code=201)
async def join_queue(
    queue_id: str, data: QueueJoinRequest, db: AsyncSession = Depends(get_db), caller: Caller = Depends(require_caller)
):
    ensure_self_or_admin(data.customer_id, caller)
    if not caller.is_admin:
        # Priority and weight decide who is served first; customers cannot set their own.
        data = data.model_copy(update={"priority": 0, "weight": 1.0})
    try:
        return await queue_service.join_queue(db, queue_id, data)
    except QueueNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except QueueFullError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.delete("/queues/{queue_id}/entries/{entry_id}", status_code=204)
async def leave_queue(queue_id: str, entry_id: str, db: AsyncSession = Depends(get_db), caller: Caller = Depends(require_caller)):
    if not caller.is_admin:
        entry = (await db.execute(select(QueueEntry).where(QueueEntry.id == entry_id))).scalar_one_or_none()
        if entry is None or entry.customer_id != caller.user_id:
            raise HTTPException(status_code=404, detail="Queue entry not found")
    try:
        await queue_service.leave_queue(db, queue_id, entry_id)
    except EntryNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/queues/{queue_id}/position/{customer_id}", response_model=QueuePositionResponse)
async def get_position(
    queue_id: str, customer_id: str, db: AsyncSession = Depends(get_db), caller: Caller = Depends(require_caller)
):
    ensure_self_or_admin(customer_id, caller)
    try:
        return await queue_service.get_position(db, queue_id, customer_id)
    except EntryNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
