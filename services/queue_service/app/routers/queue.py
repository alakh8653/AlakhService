from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import risk
from app.core.exceptions import EntryNotFoundError, QueueFullError, QueueNotFoundError
from app.core.names import FALLBACK, NameLookup, get_name_lookup
from app.core.notifier import Notifier, get_notifier
from app.database import get_db
from app.dependencies import (
    Caller,
    OwnerLookup,
    ensure_self_or_admin,
    get_service_owner_lookup,
    require_caller,
)
from app.models.queue import QueueEntry
from app.schemas.queue import (
    QueueCreate,
    QueueEntryResponse,
    QueueJoinRequest,
    QueuePositionResponse,
    QueueResponse,
    QueueUpdate,
)
from app.services.queue_service import queue_service

router = APIRouter()


async def _named(entries: List[QueueEntry], lookup_names: NameLookup) -> List[QueueEntryResponse]:
    """Entries as the shop sees them: each customer by display name, in one lookup."""
    try:
        names = await lookup_names({e.customer_id for e in entries})
    except Exception:  # never refuse the waiting list for want of a name
        names = {}
    return [
        QueueEntryResponse.model_validate(e).model_copy(
            update={"customer_display_name": names.get(e.customer_id, FALLBACK)}
        )
        for e in entries
    ]


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
    # Customers join a service's open queue; a second one would split the line.
    if await queue_service.queues_for_service(db, data.service_id):
        raise HTTPException(status_code=409, detail="This service already has an open queue")
    return await queue_service.create_queue(db, data)


@router.get("/queues", response_model=List[QueueResponse])
async def list_queues(
    service_id: str,
    include_closed: bool = False,
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(require_caller),
):
    """A service's queues: those open to customers, or all of them for the shop to manage."""
    return await queue_service.queues_for_service(db, service_id, include_closed=include_closed)


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


async def _tell_who_is_next(
    db: AsyncSession, queue_id: str, background: BackgroundTasks, notifier: Notifier, called=None
) -> None:
    """After the line moves: commit, then tell the called customer and anyone now near the front."""
    notices = await queue_service.soon_notices(db, queue_id)
    await db.commit()  # visible before anyone is told
    if called is not None:
        background.add_task(
            notifier.send, "queue.called", [{"user_id": called.customer_id, "role": "customer"}], {"queue_id": queue_id}
        )
    for n in notices:
        background.add_task(
            notifier.send,
            "queue.almost_turn",
            [{"user_id": n.customer_id, "role": "customer"}],
            {"queue_id": queue_id, "people_ahead": n.people_ahead, "minutes": n.estimated_wait_minutes},
        )


@router.delete("/queues/{queue_id}/entries/{entry_id}", status_code=204)
async def leave_queue(
    queue_id: str,
    entry_id: str,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(require_caller),
    notifier: Notifier = Depends(get_notifier),
):
    if not caller.is_admin:
        entry = (await db.execute(select(QueueEntry).where(QueueEntry.id == entry_id))).scalar_one_or_none()
        if entry is None or entry.customer_id != caller.user_id:
            raise HTTPException(status_code=404, detail="Queue entry not found")
    try:
        await queue_service.leave_queue(db, queue_id, entry_id)
    except EntryNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    await _tell_who_is_next(db, queue_id, background, notifier)


@router.get("/queues/{queue_id}/position/{customer_id}", response_model=QueuePositionResponse)
async def get_position(
    queue_id: str, customer_id: str, db: AsyncSession = Depends(get_db), caller: Caller = Depends(require_caller)
):
    ensure_self_or_admin(customer_id, caller)
    try:
        return await queue_service.get_position(db, queue_id, customer_id)
    except EntryNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


async def _owned_queue(db: AsyncSession, queue_id: str, caller: Caller, lookup_owner: OwnerLookup):
    """The queue, if the caller owns the shop offering its service (or is an admin)."""
    try:
        queue = await queue_service.get_queue(db, queue_id)
    except QueueNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    if not caller.is_admin and await lookup_owner(queue.service_id) != caller.user_id:
        raise HTTPException(status_code=403, detail="Not your shop")
    return queue


@router.get("/queues/{queue_id}/entries", response_model=List[QueueEntryResponse])
async def waiting_list(
    queue_id: str,
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(require_caller),
    lookup_owner: OwnerLookup = Depends(get_service_owner_lookup),
    lookup_names: NameLookup = Depends(get_name_lookup),
):
    """Who is being served (CALLED, position 0) and who is waiting, in serving order (the shop only)."""
    await _owned_queue(db, queue_id, caller, lookup_owner)
    return await _named(await queue_service.waiting_list(db, queue_id), lookup_names)


@router.post("/queues/{queue_id}/next", response_model=Optional[QueueEntryResponse])
async def call_next(
    queue_id: str,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(require_caller),
    lookup_owner: OwnerLookup = Depends(get_service_owner_lookup),
    notifier: Notifier = Depends(get_notifier),
    lookup_names: NameLookup = Depends(get_name_lookup),
):
    """Calls the next customer (the shop only); they are told it is their turn. Null when nobody is waiting."""
    await _owned_queue(db, queue_id, caller, lookup_owner)
    entry, no_shows = await queue_service.call_next(db, queue_id)
    await _tell_who_is_next(db, queue_id, background, notifier, called=entry)
    for skipped in no_shows:
        background.add_task(risk.report_risk, skipped.customer_id, *risk.NO_SHOW)
    return (await _named([entry], lookup_names))[0] if entry else None


@router.post("/queues/{queue_id}/entries/{entry_id}/complete", response_model=QueueEntryResponse)
async def complete_entry(
    queue_id: str,
    entry_id: str,
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(require_caller),
    lookup_owner: OwnerLookup = Depends(get_service_owner_lookup),
    lookup_names: NameLookup = Depends(get_name_lookup),
):
    """The shop finished serving a called customer; the time taken refines the queue's wait estimates."""
    await _owned_queue(db, queue_id, caller, lookup_owner)
    try:
        entry = await queue_service.complete(db, queue_id, entry_id)
    except EntryNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return (await _named([entry], lookup_names))[0]


@router.post("/queues/{queue_id}/entries/{entry_id}/no-show", response_model=QueueEntryResponse)
async def no_show_entry(
    queue_id: str,
    entry_id: str,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(require_caller),
    lookup_owner: OwnerLookup = Depends(get_service_owner_lookup),
    lookup_names: NameLookup = Depends(get_name_lookup),
):
    """A called customer did not turn up (the shop only). Called customers are also skipped
    automatically after the queue's grace period, the next time the shop calls someone."""
    await _owned_queue(db, queue_id, caller, lookup_owner)
    try:
        entry = await queue_service.no_show(db, queue_id, entry_id)
    except EntryNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    await db.commit()
    background.add_task(risk.report_risk, entry.customer_id, *risk.NO_SHOW)
    return (await _named([entry], lookup_names))[0]


@router.patch("/queues/{queue_id}", response_model=QueueResponse)
async def update_queue(
    queue_id: str,
    data: QueueUpdate,
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(require_caller),
    lookup_owner: OwnerLookup = Depends(get_service_owner_lookup),
):
    """Opens or closes the queue to new customers (those already waiting stay), or changes how many
    staff serve it and its minutes per customer (the shop only)."""
    await _owned_queue(db, queue_id, caller, lookup_owner)
    return await queue_service.update_settings(db, queue_id, data)
