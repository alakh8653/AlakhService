"""Today's live queue at a shop: what customers see, what the shop runs it with, and the public board.

Customers: GET /bookings/{id}/queue (their place, wait range, who serves them), POST /bookings/{id}/check-in,
POST /bookings/walk-in (join a shop's line now).
The shop (owner or admin): GET /bookings/shop/{shop_id}/queue (the whole line), walk-ins, call next,
reorder, VIP, no-show, team status (breaks, off today) and queue settings. Every change is audited.
Anyone: GET /bookings/shop/{shop_id}/queue/board, a masked board for a screen at the shop (ETag/304).
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Response, WebSocket
from fastapi.websockets import WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import availability, live_queue, payments, queue_ops, risk
from app.core import queue_engine as qe
from app.core.access import ADMIN, CUSTOMER, SHOP_OWNER, OwnerLookup
from app.core.fsm import AT_SHOP, BookingStatus
from app.core.names import NameLookup, get_name_lookup
from app.core.notifier import Notifier, get_notifier, notify_booking, snapshot
from app.core.payments import PaymentClient, get_payment_client, get_session_factory
from app.core.queue_hub import hub, version_of
from app.database import get_db
from app.dependencies import (
    ScheduleLookup,
    get_clock,
    get_current_user,
    get_schedule_lookup,
    get_service_lookup,
    get_shop_owner_lookup,
    get_team_lookup,
    require_shop_access,
    verify_access_token,
)
from app.models.booking import Booking
from app.routers.bookings import (
    WS_FORBIDDEN,
    WS_TRY_AGAIN_LATER,
    WS_UNAUTHENTICATED,
    _visible_booking,
    manager,
)
from app.schemas.booking import BookingCreate, QueueStatus, ShopQueueEntry
from app.services.booking_service import booking_service

router = APIRouter()

# What a screen at the shop shows: who is being served and the next few, names masked.
BOARD_NEXT = 8
FAR_FUTURE = datetime.max.replace(tzinfo=timezone.utc)


class QueueSettingsBody(BaseModel):
    buffer_pct: float = Field(0.0, ge=0, le=1)
    alpha: float = Field(0.2, gt=0, le=1)
    grace_minutes: int = Field(10, ge=0, le=120)
    aging_minutes: int = Field(20, ge=1, le=480)
    check_in_required: bool = False
    vip_per_day: int = Field(5, ge=0, le=100)


class TeamStatusBody(BaseModel):
    status: Literal["AVAILABLE", "BREAK", "OFF"]
    # How long a break lasts.
    minutes: Optional[int] = Field(None, ge=1, le=240)


class Shift(BaseModel):
    start: datetime
    end: datetime


class TeamMemberState(BaseModel):
    staff_id: str
    name: Optional[str] = None
    service_ids: List[str] = []
    status: str
    until: Optional[datetime] = None
    serving_booking_id: Optional[str] = None
    serving_name: Optional[str] = None
    serving_since: Optional[datetime] = None
    serving_until: Optional[datetime] = None
    overrun: bool = False
    # Customers the queue has planned for them today.
    waiting: int = 0
    # When they work today, for a member with their own hours ([] means not today); null means the
    # shop's hours.
    works_today: Optional[List[Shift]] = None


class WalkInBody(BaseModel):
    service_id: str
    # Who the shop calls out (no account needed).
    name: str = Field(..., min_length=1, max_length=80)
    vip: bool = False
    preferred_staff_id: Optional[str] = None


class JoinBody(BaseModel):
    service_id: str
    preferred_staff_id: Optional[str] = None


class CallNextBody(BaseModel):
    # The team member who is free (none for a shop without a team).
    staff_id: Optional[str] = None


class ReorderBody(BaseModel):
    # The waiting customers in the order the shop wants them; anyone left out goes by the usual rules after.
    booking_ids: List[str] = Field(..., min_length=1, max_length=200)


class PriorityBody(BaseModel):
    vip: bool


class BoardRow(BaseModel):
    ticket: str
    name: str
    staff_name: Optional[str] = None
    wait_minutes: Optional[int] = None


class Board(BaseModel):
    version: str
    now_serving: List[BoardRow]
    next: List[BoardRow]
    waiting: int


# ---------------------------------------------------------------------------------------------- helpers


async def _schedule(lookup_schedule: ScheduleLookup, shop_id: Optional[str]) -> availability.Schedule:
    return availability.Schedule.from_shop_service(await lookup_schedule(shop_id) if shop_id else None)


def _is_today(schedule: availability.Schedule, at: datetime, now: datetime) -> bool:
    return schedule.local(live_queue._utc(at)).date() == schedule.local(now).date()


def queue_status(
    booking: Booking,
    spot: Optional[live_queue.QueueSpot],
    schedule: availability.Schedule,
    team: List[dict],
    now: datetime,
) -> QueueStatus:
    today = _is_today(schedule, booking.scheduled_at, now)
    waiting = booking.status in live_queue.WAITING
    can_check_in = booking.service_mode == AT_SHOP and today and waiting and booking.checked_in_at is None
    if spot is None:
        state = live_queue.NOT_QUEUED if today or booking.service_mode != AT_SHOP else live_queue.NOT_TODAY
        return QueueStatus(booking_id=booking.id, state=state, scheduled_at=booking.scheduled_at)
    names = {m["id"]: m.get("name") for m in team}
    return QueueStatus(
        booking_id=booking.id,
        state=spot.state,
        scheduled_at=booking.scheduled_at,
        position=spot.position,
        people_ahead=spot.people_ahead,
        being_served=spot.being_served,
        estimated_start=spot.estimated_start,
        wait_minutes=spot.wait_minutes,
        running_late_minutes=spot.running_late_minutes,
        capacity=len(team) or schedule.capacity,
        eta_min=spot.eta_min,
        eta_max=spot.eta_max,
        confidence=spot.confidence,
        staff_name=names.get(spot.worker_id),
        ahead_with_staff=spot.ahead_on_worker if spot.estimated_start else None,
        reason=spot.reason,
        checked_in=booking.checked_in_at is not None,
        can_check_in=can_check_in,
    )


async def _line(db, shop_id, lookup_schedule, lookup_team, now):
    schedule = await _schedule(lookup_schedule, shop_id)
    team = await queue_ops.team_of(lookup_team, shop_id)
    spots = await live_queue.shop_queue(db, shop_id, schedule, now, team)
    return schedule, team, spots


def _order(spots: Dict[str, live_queue.QueueSpot]) -> List[live_queue.QueueSpot]:
    rank = {live_queue.IN_PROGRESS: 0, live_queue.YOUR_TURN: 1, live_queue.WAITING_STATE: 1}
    return sorted(
        spots.values(),
        key=lambda s: (rank.get(s.state, 2), s.position or 0, s.estimated_start or FAR_FUTURE, s.booking_id),
    )


async def _require_shop_booking(db, booking_id, user, lookup_owner) -> Booking:
    booking, parties = await _visible_booking(db, booking_id, user, lookup_owner)
    if not parties & {ADMIN, SHOP_OWNER}:
        raise HTTPException(status_code=403, detail="Only the shop can change its line")
    if booking.service_mode != AT_SHOP or not booking.shop_id:
        raise HTTPException(status_code=400, detail="Only visits at the shop are in its line")
    return booking


def _display(booking: Booking, names: dict) -> str:
    return booking.walk_in_name or names.get(booking.customer_id) or "Customer"


def _mask(name: str) -> str:
    """First name's first letter and the rest hidden (a screen anyone in the shop can see)."""
    first = (name or "Customer").strip().split(" ")[0] or "Customer"
    return first[0].upper() + "•" * min(4, max(2, len(first) - 1))


async def _created(db, notifier, booking: Booking, lookup_owner, background, service_name: Optional[str]):
    await manager.broadcast(booking.id, {"booking_id": booking.id, "status": booking.status})
    await db.commit()
    hub.poke(booking.shop_id)
    background.add_task(
        notify_booking, notifier, snapshot(booking, service_name), "booking.created", booking.customer_id,
        lookup_owner, roles=("shop",),
    )  # fmt: skip


async def _new_walk_in(
    db: AsyncSession,
    listing: dict,
    customer_id: str,
    now: datetime,
    *,
    name: Optional[str],
    priority: int,
    checked_in: bool,
    preferred: Optional[dict],
    actor_id: str,
) -> Booking:
    data = BookingCreate(
        service_id=listing["id"],
        scheduled_at=now,
        duration_minutes=listing.get("duration_minutes") or 30,
        total_amount=listing["price_cents"],
        shop_id=listing["shop_id"],
        customer_id=customer_id,
    )
    meta = None
    if preferred:
        meta = json.dumps({"preferred_staff_id": preferred["id"], "preferred_staff_name": preferred.get("name")})
    booking = await booking_service.create_booking(db, customer_id, data, meta, booking_id=str(uuid.uuid4()))
    # The shop's clock, strictly after the last one to join (the caller holds the shop's lock): ticket order.
    latest = await queue_ops.last_joined(db, listing["shop_id"])
    booking.created_at = max(now, latest + timedelta(microseconds=1)) if latest else now
    booking.source = live_queue.WALK_IN
    booking.priority = priority
    booking.walk_in_name = name
    booking.checked_in_at = now if checked_in else None
    await booking_service.transition_status(
        db, booking.id, BookingStatus.CONFIRMED.value, actor_id, "Joined the line on the day"
    )
    await live_queue.audit(db, listing["shop_id"], booking.id, "walk_in", actor_id, {"vip": priority == qe.VIP}, at=now)
    return booking


async def _listing_for(lookup_service, service_id: str, shop_id: Optional[str] = None) -> dict:
    listing = await lookup_service(service_id)
    if listing is None or (shop_id and listing.get("shop_id") != shop_id):
        raise HTTPException(status_code=404, detail="Service not found")
    if not listing.get("is_active", False):
        raise HTTPException(status_code=409, detail="Service is not currently offered")
    if AT_SHOP not in (listing.get("service_modes") or [AT_SHOP]):
        raise HTTPException(status_code=422, detail="This service is not offered at the shop")
    return {**listing, "id": listing.get("id") or service_id}


def _preferred(team: List[dict], staff_id: Optional[str], service_id: str) -> Optional[dict]:
    if not staff_id:
        return None
    member = next((m for m in team if m["id"] == staff_id), None)
    if member is None or not queue_ops.can_do(member, service_id):
        raise HTTPException(status_code=422, detail="That professional does not do this service here")
    return member


async def start_service(
    db, booking: Booking, staff_id: Optional[str], user_id: str, team, spots, now: datetime
) -> Booking:
    """Starts the service (confirming it first if needed). 409 when that team member is busy."""
    try:
        if booking.status == BookingStatus.PENDING.value:
            await booking_service.transition_status(db, booking.id, BookingStatus.CONFIRMED.value, user_id, "Called in")
        booking = await booking_service.transition_status(
            db, booking.id, BookingStatus.IN_PROGRESS.value, user_id, "Service started"
        )
        await queue_ops.begin_service(db, booking, staff_id, team, spots, now)
        await db.flush()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(status_code=409, detail="That team member is already serving someone") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return booking


# ---------------------------------------------------------------------------------------------- customers


@router.get("/bookings/{booking_id}/queue", response_model=QueueStatus)
async def booking_queue(
    booking_id: str,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
    lookup_schedule: ScheduleLookup = Depends(get_schedule_lookup),
    lookup_team=Depends(get_team_lookup),
    clock: Callable[[], datetime] = Depends(get_clock),
):
    """Where the booking stands in today's queue at its shop: place in line, wait range, who serves them."""
    booking, _ = await _visible_booking(db, booking_id, current_user, lookup_owner)
    schedule = await _schedule(lookup_schedule, booking.shop_id)
    now = live_queue._utc(clock())
    team = await queue_ops.team_of(lookup_team, booking.shop_id) if booking.service_mode == AT_SHOP else []
    spot = await live_queue.spot_for(db, booking, schedule, now, team)
    return queue_status(booking, spot, schedule, team, now)


@router.post("/bookings/{booking_id}/check-in", response_model=QueueStatus)
async def check_in(
    booking_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
    lookup_schedule: ScheduleLookup = Depends(get_schedule_lookup),
    lookup_team=Depends(get_team_lookup),
    clock: Callable[[], datetime] = Depends(get_clock),
):
    """The customer has arrived (they say so, or the shop does). Arriving after the grace period puts them
    in the line from now."""
    booking, parties = await _visible_booking(db, booking_id, current_user, lookup_owner)
    if not parties & {ADMIN, SHOP_OWNER, CUSTOMER}:
        raise HTTPException(status_code=403, detail="Only the customer or the shop can check in")
    schedule = await _schedule(lookup_schedule, booking.shop_id)
    now = live_queue._utc(clock())
    if booking.service_mode != AT_SHOP or not _is_today(schedule, booking.scheduled_at, now):
        raise HTTPException(status_code=409, detail="Check-in is for today's visits at the shop")
    if booking.status not in live_queue.WAITING:
        raise HTTPException(status_code=409, detail="This visit is not waiting")
    if booking.checked_in_at is None:
        booking.checked_in_at = now
        late = now > live_queue._utc(booking.scheduled_at) + timedelta(
            minutes=(await live_queue.settings_for(db, booking.shop_id)).grace_minutes
        )
        await live_queue.audit(
            db, booking.shop_id, booking.id, "check_in", current_user.get("sub"), {"late": late}, at=now
        )
        await db.commit()
        hub.poke(booking.shop_id)
    team = await queue_ops.team_of(lookup_team, booking.shop_id)
    spot = await live_queue.spot_for(db, booking, schedule, now, team)
    return queue_status(booking, spot, schedule, team, now)


@router.post("/bookings/walk-in", response_model=QueueStatus, status_code=201)
async def join_line(
    body: JoinBody,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    lookup_service=Depends(get_service_lookup),
    lookup_schedule: ScheduleLookup = Depends(get_schedule_lookup),
    lookup_team=Depends(get_team_lookup),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
    notifier: Notifier = Depends(get_notifier),
    clock: Callable[[], datetime] = Depends(get_clock),
):
    """Joins a shop's line now, without a booked time: the customer gets a place and a wait at once."""
    customer_id = current_user.get("sub")
    listing = await _listing_for(lookup_service, body.service_id)
    shop_id = listing["shop_id"]
    schedule = await _schedule(lookup_schedule, shop_id)
    now = live_queue._utc(clock())
    if not schedule.accepting_bookings:
        raise HTTPException(status_code=409, detail=availability.NOT_ACCEPTING_MESSAGE)
    if not queue_ops.open_now(schedule, now):
        raise HTTPException(status_code=409, detail="The shop is closed now: book a time instead")
    await booking_service.hold_shop_capacity(db, shop_id)  # one join at a time per shop
    earlier = await queue_ops.walk_ins_today(db, customer_id, shop_id, schedule, now)
    if any(b.status in (*live_queue.WAITING, live_queue.SERVING) for b in earlier):
        raise HTTPException(status_code=409, detail="You are already in this shop's line")
    if len(earlier) >= queue_ops.WALK_INS_PER_DAY:
        raise HTTPException(status_code=429, detail="You have joined this shop's line too often today")
    team = await queue_ops.team_of(lookup_team, shop_id)
    preferred = _preferred(team, body.preferred_staff_id, body.service_id)
    booking = await _new_walk_in(
        db, listing, customer_id, now, name=None, priority=qe.WALK_IN, checked_in=False, preferred=preferred,
        actor_id=customer_id,
    )  # fmt: skip
    spots = await live_queue.shop_queue(db, shop_id, schedule, now, team)
    spot = spots.get(booking.id)
    if spot is None or spot.state == live_queue.UNSERVABLE:
        await db.rollback()
        raise HTTPException(status_code=409, detail="The line is full for today: book a time instead")
    await _created(db, notifier, booking, lookup_owner, background, listing.get("name"))
    return queue_status(booking, spot, schedule, team, now)


# ---------------------------------------------------------------------------------------------- the shop


@router.get("/bookings/shop/{shop_id}/queue", response_model=list[ShopQueueEntry])
async def shop_queue(
    shop_id: str = Depends(require_shop_access),
    db: AsyncSession = Depends(get_db),
    lookup_schedule: ScheduleLookup = Depends(get_schedule_lookup),
    lookup_team=Depends(get_team_lookup),
    lookup_names: NameLookup = Depends(get_name_lookup),
    clock: Callable[[], datetime] = Depends(get_clock),
):
    """Today's queue at the shop, in order: who is being served (by whom), who is next, wait ranges."""
    now = live_queue._utc(clock())
    _, team, spots = await _line(db, shop_id, lookup_schedule, lookup_team, now)
    if not spots:
        return []
    settings = await live_queue.settings_for(db, shop_id)
    bookings = {b.id: b for b in await booking_service.get_bookings(db, list(spots))}
    names = await lookup_names([b.customer_id for b in bookings.values() if not b.walk_in_name])
    staff = {m["id"]: m.get("name") for m in team}
    entries = []
    for s in _order(spots):
        b = bookings[s.booking_id]
        entries.append(
            ShopQueueEntry(
                booking_id=s.booking_id,
                booking_number=b.booking_number,
                customer_display_name=_display(b, names),
                state=s.state,
                position=s.position,
                scheduled_at=b.scheduled_at,
                estimated_start=s.estimated_start,
                running_late_minutes=s.running_late_minutes,
                service_id=b.service_id,
                source=b.source or live_queue.BOOKED,
                priority=live_queue.PRIORITY_NAMES.get(b.priority, "APPOINTMENT"),
                checked_in=b.checked_in_at is not None,
                staff_id=s.worker_id if s.worker_id in staff else None,
                staff_name=staff.get(s.worker_id),
                eta_min=s.eta_min,
                eta_max=s.eta_max,
                estimated_end=s.estimated_end,
                confidence=s.confidence,
                reason=s.reason,
                overrun=s.overrun,
                moved=b.queue_rank is not None,
                can_mark_no_show=queue_ops.no_show_problem(b, settings, now) is None,
            )
        )
    return entries


async def board_content(db, shop_id, lookup_schedule, lookup_team, lookup_names, now) -> Board:
    _, team, spots = await _line(db, shop_id, lookup_schedule, lookup_team, now)
    bookings = {b.id: b for b in await booking_service.get_bookings(db, list(spots))} if spots else {}
    names = await lookup_names([b.customer_id for b in bookings.values() if not b.walk_in_name]) if bookings else {}
    staff = {m["id"]: m.get("name") for m in team}

    def row(s):
        b = bookings[s.booking_id]
        return BoardRow(
            ticket=b.booking_number[-4:],
            name=_mask(_display(b, names)),
            staff_name=staff.get(s.worker_id),
            wait_minutes=s.wait_minutes if s.state != live_queue.IN_PROGRESS else None,
        )

    ordered = _order(spots)
    serving = [row(s) for s in ordered if s.state == live_queue.IN_PROGRESS]
    waiting = [s for s in ordered if s.state in (live_queue.WAITING_STATE, live_queue.YOUR_TURN)]
    content = {"now_serving": serving, "next": [row(s) for s in waiting[:BOARD_NEXT]], "waiting": len(waiting)}
    version = version_of({k: [r.model_dump() for r in v] if isinstance(v, list) else v for k, v in content.items()})
    return Board(version=version, **content)


@router.get("/bookings/shop/{shop_id}/queue/board", response_model=Board)
async def board(
    shop_id: str,
    response: Response,
    if_none_match: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
    lookup_schedule: ScheduleLookup = Depends(get_schedule_lookup),
    lookup_team=Depends(get_team_lookup),
    lookup_names: NameLookup = Depends(get_name_lookup),
    clock: Callable[[], datetime] = Depends(get_clock),
):
    """A screen at the shop: who is being served and who is next, by ticket and a masked name. Public;
    the version (also the ETag) changes only when something on it does, so a screen polls cheaply (or
    listens on /ws/shops/{shop_id}/board)."""
    content = await board_content(db, shop_id, lookup_schedule, lookup_team, lookup_names, live_queue._utc(clock()))
    etag = f'"{content.version}"'
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "no-cache"
    if if_none_match == etag:
        return Response(status_code=304, headers={"ETag": etag})
    return content


async def _live(websocket: WebSocket, shop_id: str, view: str, build) -> None:
    await websocket.accept()
    if not await hub.join(shop_id, view, websocket, build):
        return
    try:
        while True:
            if await websocket.receive_text() == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        hub.leave(shop_id, view, websocket)


@router.websocket("/ws/shops/{shop_id}/queue")
async def shop_queue_socket(
    shop_id: str,
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
    lookup_schedule: ScheduleLookup = Depends(get_schedule_lookup),
    lookup_team=Depends(get_team_lookup),
    lookup_names: NameLookup = Depends(get_name_lookup),
    clock: Callable[[], datetime] = Depends(get_clock),
    session_factory=Depends(get_session_factory),
):
    """The shop's whole line, live: {"type": "queue", "version", "entries"} on joining and on every change."""
    # Browsers cannot set headers on a WebSocket handshake, so the access token comes as ?token=.
    try:
        user = verify_access_token(token or "")
    except HTTPException:
        await websocket.close(code=WS_UNAUTHENTICATED)
        return
    try:
        allowed = user.get("role") == ADMIN or await lookup_owner(shop_id) == user.get("sub")
    except HTTPException:
        await websocket.close(code=WS_TRY_AGAIN_LATER)
        return
    if not allowed:
        await websocket.close(code=WS_FORBIDDEN)
        return

    async def build():
        async with session_factory() as db:
            entries = await shop_queue(shop_id, db, lookup_schedule, lookup_team, lookup_names, clock)
        rows = [e.model_dump(mode="json") for e in entries]
        version = version_of(rows)
        return version, {"type": "queue", "shop_id": shop_id, "version": version, "entries": rows}

    await _live(websocket, shop_id, "shop", build)


@router.websocket("/ws/shops/{shop_id}/board")
async def board_socket(
    shop_id: str,
    websocket: WebSocket,
    lookup_schedule: ScheduleLookup = Depends(get_schedule_lookup),
    lookup_team=Depends(get_team_lookup),
    lookup_names: NameLookup = Depends(get_name_lookup),
    clock: Callable[[], datetime] = Depends(get_clock),
    session_factory=Depends(get_session_factory),
):
    """The public board, live: {"type": "board", ...the board} on joining and on every change."""

    async def build():
        async with session_factory() as db:
            content = await board_content(
                db, shop_id, lookup_schedule, lookup_team, lookup_names, live_queue._utc(clock())
            )
        return content.version, {"type": "board", "shop_id": shop_id, **content.model_dump(mode="json")}

    await _live(websocket, shop_id, "board", build)


@router.post("/bookings/shop/{shop_id}/walk-ins", response_model=ShopQueueEntry, status_code=201)
async def add_walk_in(
    body: WalkInBody,
    background: BackgroundTasks,
    shop_id: str = Depends(require_shop_access),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    lookup_service=Depends(get_service_lookup),
    lookup_schedule: ScheduleLookup = Depends(get_schedule_lookup),
    lookup_team=Depends(get_team_lookup),
    lookup_names: NameLookup = Depends(get_name_lookup),
    clock: Callable[[], datetime] = Depends(get_clock),
):
    """Someone at the counter joins the line (no account needed): they are checked in and get a place."""
    actor = current_user.get("sub")
    listing = await _listing_for(lookup_service, body.service_id, shop_id)
    schedule = await _schedule(lookup_schedule, shop_id)
    now = live_queue._utc(clock())
    await booking_service.hold_shop_capacity(db, shop_id)
    team = await queue_ops.team_of(lookup_team, shop_id)
    preferred = _preferred(team, body.preferred_staff_id, body.service_id)
    if body.vip:
        settings = await live_queue.settings_for(db, shop_id)
        if await queue_ops.vips_today(db, shop_id, schedule, now) >= settings.vip_per_day:
            raise HTTPException(
                status_code=409, detail=f"At most {settings.vip_per_day} VIPs a day keeps the line fair"
            )
    booking = await _new_walk_in(
        db, listing, live_queue.WALK_IN_PREFIX + str(uuid.uuid4()), now, name=body.name.strip(),
        priority=qe.VIP if body.vip else qe.WALK_IN, checked_in=True, preferred=preferred, actor_id=actor,
    )  # fmt: skip
    if body.vip:
        await live_queue.audit(db, shop_id, booking.id, "vip", actor, {"vip": True}, at=now)
    booking_id = booking.id
    await db.commit()
    hub.poke(shop_id)
    entries = await shop_queue(shop_id, db, lookup_schedule, lookup_team, lookup_names, clock)
    return next(e for e in entries if e.booking_id == booking_id)


@router.post("/bookings/shop/{shop_id}/queue/call-next", response_model=ShopQueueEntry)
async def call_next(
    body: CallNextBody,
    background: BackgroundTasks,
    shop_id: str = Depends(require_shop_access),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    lookup_schedule: ScheduleLookup = Depends(get_schedule_lookup),
    lookup_team=Depends(get_team_lookup),
    lookup_names: NameLookup = Depends(get_name_lookup),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
    notifier: Notifier = Depends(get_notifier),
    clock: Callable[[], datetime] = Depends(get_clock),
):
    """A team member is free: starts the next customer the queue planned for them (or the next anyone may
    take). 409 when nobody is waiting for them."""
    user_id = current_user.get("sub")
    now = live_queue._utc(clock())
    await booking_service.hold_shop_capacity(db, shop_id)
    _, team, spots = await _line(db, shop_id, lookup_schedule, lookup_team, now)
    members = {m["id"]: m for m in team}
    if body.staff_id and body.staff_id not in members:
        raise HTTPException(status_code=422, detail="That team member is not on this shop's team")
    waiting = [s for s in _order(spots) if s.state in (live_queue.WAITING_STATE, live_queue.YOUR_TURN)]
    if body.staff_id:
        bookings = {b.id: b for b in await booking_service.get_bookings(db, [s.booking_id for s in waiting])}
        mine = [s for s in waiting if s.worker_id == body.staff_id]
        others = [
            s for s in waiting
            if queue_ops.can_do(members[body.staff_id], bookings[s.booking_id].service_id)
            and bookings[s.booking_id].preferred_staff_id in (None, body.staff_id)
            and (s.estimated_start or now) <= now + timedelta(minutes=5)
        ]  # fmt: skip
        waiting = mine[:1] or others[:1]
    if not waiting:
        raise HTTPException(status_code=409, detail="Nobody is waiting for this team member now")
    booking = await booking_service.get_booking(db, waiting[0].booking_id)
    booking = await start_service(db, booking, body.staff_id, user_id, team, spots, now)
    await live_queue.audit(
        db, shop_id, booking.id, "call_next", user_id, {"staff_id": booking.served_by_staff_id}, at=now
    )
    booking_id = booking.id
    await manager.broadcast(booking_id, {"booking_id": booking_id, "status": booking.status})
    await db.commit()
    hub.poke(shop_id)
    background.add_task(notify_booking, notifier, snapshot(booking), "booking.in_progress", user_id, lookup_owner)
    entries = await shop_queue(shop_id, db, lookup_schedule, lookup_team, lookup_names, clock)
    return next(e for e in entries if e.booking_id == booking_id)


@router.post("/bookings/shop/{shop_id}/queue/reorder", response_model=list[ShopQueueEntry])
async def reorder(
    body: ReorderBody,
    shop_id: str = Depends(require_shop_access),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    lookup_schedule: ScheduleLookup = Depends(get_schedule_lookup),
    lookup_team=Depends(get_team_lookup),
    lookup_names: NameLookup = Depends(get_name_lookup),
    clock: Callable[[], datetime] = Depends(get_clock),
):
    """Puts the listed waiting customers first, in this order (audited)."""
    now = live_queue._utc(clock())
    await booking_service.hold_shop_capacity(db, shop_id)
    _, _, spots = await _line(db, shop_id, lookup_schedule, lookup_team, now)
    waiting = {s.booking_id for s in spots.values() if s.state in (live_queue.WAITING_STATE, live_queue.YOUR_TURN)}
    if len(set(body.booking_ids)) != len(body.booking_ids) or not set(body.booking_ids) <= waiting:
        raise HTTPException(status_code=422, detail="List only customers waiting in today's line, once each")
    rank = {bid: i + 1.0 for i, bid in enumerate(body.booking_ids)}
    for b in await booking_service.get_bookings(db, list(waiting)):
        b.queue_rank = rank.get(b.id)
    await live_queue.audit(db, shop_id, None, "reorder", current_user.get("sub"), {"order": body.booking_ids}, at=now)
    await db.commit()
    hub.poke(shop_id)
    return await shop_queue(shop_id, db, lookup_schedule, lookup_team, lookup_names, clock)


@router.put("/bookings/{booking_id}/priority", response_model=QueueStatus)
async def set_priority(
    booking_id: str,
    body: PriorityBody,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
    lookup_schedule: ScheduleLookup = Depends(get_schedule_lookup),
    lookup_team=Depends(get_team_lookup),
    clock: Callable[[], datetime] = Depends(get_clock),
):
    """Makes a waiting customer a VIP (served first; a few a day) or a regular again."""
    booking = await _require_shop_booking(db, booking_id, current_user, lookup_owner)
    if booking.status not in live_queue.WAITING:
        raise HTTPException(status_code=409, detail="This visit is not waiting")
    schedule = await _schedule(lookup_schedule, booking.shop_id)
    now = live_queue._utc(clock())
    regular = qe.WALK_IN if booking.source == live_queue.WALK_IN else qe.APPOINTMENT
    if body.vip and booking.priority != qe.VIP:
        settings = await live_queue.settings_for(db, booking.shop_id)
        if await queue_ops.vips_today(db, booking.shop_id, schedule, now) >= settings.vip_per_day:
            raise HTTPException(
                status_code=409, detail=f"At most {settings.vip_per_day} VIPs a day keeps the line fair"
            )
    booking.priority = qe.VIP if body.vip else regular
    await live_queue.audit(
        db, booking.shop_id, booking.id, "vip" if body.vip else "regular", current_user.get("sub"), at=now
    )
    await db.commit()
    hub.poke(booking.shop_id)
    team = await queue_ops.team_of(lookup_team, booking.shop_id)
    spot = await live_queue.spot_for(db, booking, schedule, now, team)
    return queue_status(booking, spot, schedule, team, now)


@router.post("/bookings/{booking_id}/no-show", response_model=QueueStatus)
async def mark_no_show(
    booking_id: str,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
    lookup_schedule: ScheduleLookup = Depends(get_schedule_lookup),
    notifier: Notifier = Depends(get_notifier),
    payment_client: PaymentClient = Depends(get_payment_client),
    session_factory=Depends(get_session_factory),
    clock: Callable[[], datetime] = Depends(get_clock),
):
    """The customer did not come: cancelled as a no-show after the grace period (the refund follows the
    customer's late-cancellation rule) and the line moves up."""
    booking = await _require_shop_booking(db, booking_id, current_user, lookup_owner)
    now = live_queue._utc(clock())
    settings = await live_queue.settings_for(db, booking.shop_id)
    problem = queue_ops.no_show_problem(booking, settings, now)
    if problem:
        raise HTTPException(status_code=409, detail=problem)
    user_id = current_user.get("sub")
    booking = await booking_service.cancel_booking(db, booking.id, user_id, live_queue.NO_SHOW_REASON)
    queued = await payments.enqueue(db, booking, payments.CANCELLED, "customer")
    await live_queue.audit(db, booking.shop_id, booking.id, "no_show", user_id, at=now)
    await manager.broadcast(booking.id, {"booking_id": booking.id, "status": booking.status})
    await db.commit()
    hub.poke(booking.shop_id)
    background.add_task(payments.deliver_now, session_factory, payment_client, queued.id)
    background.add_task(
        notify_booking, notifier, snapshot(booking), "booking.no_show", user_id, lookup_owner, roles=("customer",)
    )
    background.add_task(risk.report_risk, booking.customer_id, "no_show", 0.6, True)
    schedule = await _schedule(lookup_schedule, booking.shop_id)
    return queue_status(booking, None, schedule, [], now)


@router.get("/bookings/shop/{shop_id}/queue/team", response_model=list[TeamMemberState])
async def team_state(
    shop_id: str = Depends(require_shop_access),
    db: AsyncSession = Depends(get_db),
    lookup_schedule: ScheduleLookup = Depends(get_schedule_lookup),
    lookup_team=Depends(get_team_lookup),
    lookup_names: NameLookup = Depends(get_name_lookup),
    clock: Callable[[], datetime] = Depends(get_clock),
):
    """Each team member today: available, on a break (until when) or off, who they are serving, and how many
    customers the queue has planned for them."""
    now = live_queue._utc(clock())
    schedule, team, spots = await _line(db, shop_id, lookup_schedule, lookup_team, now)
    statuses = await live_queue.statuses_for(db, shop_id, schedule, now)
    own_hours = live_queue.member_shifts(schedule, now, team)
    serving = [s for s in spots.values() if s.state == live_queue.IN_PROGRESS]
    bookings = (
        {b.id: b for b in await booking_service.get_bookings(db, [s.booking_id for s in serving])} if serving else {}
    )
    names = await lookup_names([b.customer_id for b in bookings.values() if not b.walk_in_name]) if bookings else {}
    out = []
    for m in sorted(team, key=lambda m: (m.get("name") or "", m["id"])):
        status, until = statuses.get(m["id"], (qe.AVAILABLE, None))
        if status == qe.ON_BREAK and until is not None and until <= now:
            status, until = qe.AVAILABLE, None
        current = next((s for s in serving if s.worker_id == m["id"]), None)
        b = bookings.get(current.booking_id) if current else None
        out.append(
            TeamMemberState(
                staff_id=m["id"],
                name=m.get("name"),
                service_ids=m.get("service_ids") or [],
                status=status,
                until=until,
                serving_booking_id=current.booking_id if current else None,
                serving_name=_display(b, names) if b else None,
                serving_since=current.estimated_start if current else None,
                serving_until=current.estimated_end if current else None,
                overrun=bool(current and current.overrun),
                waiting=sum(
                    1
                    for s in spots.values()
                    if s.worker_id == m["id"] and s.state in (live_queue.WAITING_STATE, live_queue.YOUR_TURN)
                ),
                works_today=([Shift(start=a, end=b) for a, b in own_hours[m["id"]]] if m["id"] in own_hours else None),
            )  # fmt: skip
        )
    return out


@router.put("/bookings/shop/{shop_id}/queue/team/{staff_id}", response_model=list[TeamMemberState])
async def set_team_status(
    staff_id: str,
    body: TeamStatusBody,
    shop_id: str = Depends(require_shop_access),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    lookup_schedule: ScheduleLookup = Depends(get_schedule_lookup),
    lookup_team=Depends(get_team_lookup),
    lookup_names: NameLookup = Depends(get_name_lookup),
    clock: Callable[[], datetime] = Depends(get_clock),
):
    """A team member goes on a break (for some minutes), is off for the rest of today, or is back. Their
    waiting customers move to whoever else can serve them (or wait for them, if they asked for them)."""
    team = await queue_ops.team_of(lookup_team, shop_id)
    if staff_id not in {m["id"] for m in team}:
        raise HTTPException(status_code=404, detail="Not on this shop's team")
    if body.status == qe.ON_BREAK and not body.minutes:
        raise HTTPException(status_code=422, detail="Say how many minutes the break lasts")
    now = live_queue._utc(clock())
    until = now + timedelta(minutes=body.minutes) if body.status == qe.ON_BREAK else None
    await live_queue.set_status(db, shop_id, staff_id, body.status, until, current_user.get("sub"), at=now)
    await db.commit()
    hub.poke(shop_id)
    return await team_state(shop_id, db, lookup_schedule, lookup_team, lookup_names, clock)


@router.get("/bookings/shop/{shop_id}/queue/settings", response_model=QueueSettingsBody)
async def get_settings(shop_id: str = Depends(require_shop_access), db: AsyncSession = Depends(get_db)):
    return QueueSettingsBody(**(await live_queue.settings_for(db, shop_id)).__dict__)


@router.put("/bookings/shop/{shop_id}/queue/settings", response_model=QueueSettingsBody)
async def put_settings(
    body: QueueSettingsBody,
    shop_id: str = Depends(require_shop_access),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    saved = await live_queue.save_settings(db, shop_id, body.model_dump())
    await live_queue.audit(db, shop_id, None, "settings", current_user.get("sub"), body.model_dump())
    await db.commit()
    hub.poke(shop_id)
    return QueueSettingsBody(**saved.__dict__)
