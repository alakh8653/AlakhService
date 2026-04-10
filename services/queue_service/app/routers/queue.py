from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.queue import QueueCreate, QueueResponse, QueueJoinRequest, QueueEntryResponse, QueuePositionResponse
from app.services.queue_service import queue_service
from app.core.exceptions import QueueNotFoundError, QueueFullError, EntryNotFoundError

router = APIRouter()


@router.post("/queues", response_model=QueueResponse, status_code=201)
async def create_queue(data: QueueCreate, db: AsyncSession = Depends(get_db)):
    return await queue_service.create_queue(db, data)


@router.get("/queues/{queue_id}", response_model=QueueResponse)
async def get_queue(queue_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await queue_service.get_queue(db, queue_id)
    except QueueNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/queues/{queue_id}/join", response_model=QueueEntryResponse, status_code=201)
async def join_queue(queue_id: str, data: QueueJoinRequest, db: AsyncSession = Depends(get_db)):
    try:
        return await queue_service.join_queue(db, queue_id, data)
    except QueueNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except QueueFullError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/queues/{queue_id}/entries/{entry_id}", status_code=204)
async def leave_queue(queue_id: str, entry_id: str, db: AsyncSession = Depends(get_db)):
    try:
        await queue_service.leave_queue(db, queue_id, entry_id)
    except EntryNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/queues/{queue_id}/position/{customer_id}", response_model=QueuePositionResponse)
async def get_position(queue_id: str, customer_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await queue_service.get_position(db, queue_id, customer_id)
    except EntryNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
