import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from typing import Awaitable, Callable, Optional

import structlog
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Header,
    HTTPException,
    Query,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import availability, risk
from app.core.access import ADMIN, PROVIDER, SHOP_OWNER, OwnerLookup, may_transition, relationships
from app.core.fsm import AT_HOME, AT_SHOP, PICKUP_DROP, BookingStatus
from app.core.notifier import Notifier, get_notifier, notify_booking, snapshot
from app.database import get_db
from app.dependencies import (
    CouponPricer,
    CouponRejected,
    ScheduleLookup,
    get_clock,
    get_coupon_pricer,
    get_current_user,
    get_schedule_lookup,
    get_service_lookup,
    get_shop_owner_lookup,
    get_staff_lookup,
    require_shop_access,
    security,
    verify_access_token,
)
from app.schemas.booking import (
    BookingAssignRequest,
    BookingCancelRequest,
    BookingCreate,
    BookingListResponse,
    BookingReadyByUpdate,
    BookingResponse,
    BookingStatusHistoryResponse,
    BookingStatusUpdate,
    ShopBookingSummary,
)
from app.services.booking_service import ProviderUnavailable, booking_service

MODE_NAMES = {AT_SHOP: "a visit to the shop", AT_HOME: "a home visit", PICKUP_DROP: "pickup & drop"}

router = APIRouter()
log = structlog.get_logger()

# WebSocket close codes: 4401/4403 mirror HTTP 401/403; 1013 is the standard "try again later".
WS_UNAUTHENTICATED = 4401
WS_FORBIDDEN = 4403
WS_TRY_AGAIN_LATER = 1013


class ConnectionManager:
    # The parties of one booking need a handful of screens open; more is someone hoarding sockets.
    MAX_PER_BOOKING = 20

    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, booking_id: str, websocket: WebSocket) -> bool:
        """Accepts the socket and adds it, or closes it again when the booking has too many."""
        await websocket.accept()
        # Counted after the accept, with no await in between, so simultaneous handshakes cannot overshoot.
        sockets = self.active_connections.setdefault(booking_id, [])
        if len(sockets) >= self.MAX_PER_BOOKING:
            await websocket.close(code=WS_TRY_AGAIN_LATER)
            return False
        sockets.append(websocket)
        return True

    def disconnect(self, booking_id: str, websocket: WebSocket):
        sockets = self.active_connections.get(booking_id)
        if sockets is None:
            return
        if websocket in sockets:
            sockets.remove(websocket)
        if not sockets:
            del self.active_connections[booking_id]

    async def broadcast(self, booking_id: str, data: dict):
        for ws in list(self.active_connections.get(booking_id, [])):
            try:
                await ws.send_json(data)
            except Exception:
                self.disconnect(booking_id, ws)


manager = ConnectionManager()


def request_hash(booking_data: BookingCreate) -> str:
    """Identifies what was asked for, so a key reused for a different booking can be told apart from a retry."""
    body = json.dumps(booking_data.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode()).hexdigest()[:32]


def replay(booking, fingerprint: str, response: Response):
    """The booking an earlier request with this key made, as long as this request asks for the same thing."""
    if booking.request_hash != fingerprint:
        raise HTTPException(status_code=422, detail="This Idempotency-Key was already used for a different booking")
    response.status_code = 200
    return booking


@router.post("/bookings", response_model=BookingResponse, status_code=201)
async def create_booking(
    booking_data: BookingCreate,
    background: BackgroundTasks,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    lookup_service: Callable[[str], Awaitable[Optional[dict]]] = Depends(get_service_lookup),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
    notifier: Notifier = Depends(get_notifier),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    price_with_coupon: CouponPricer = Depends(get_coupon_pricer),
    lookup_schedule: ScheduleLookup = Depends(get_schedule_lookup),
    clock: Callable[[], datetime] = Depends(get_clock),
    # Sent by the app with every try of one booking, so a double tap or a retry after a lost response
    # gets the booking already made rather than a second one.
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key", max_length=128, pattern=r"^[A-Za-z0-9_-]+$"),
):
    customer_id = current_user.get("sub")
    fingerprint = None
    if idempotency_key:
        fingerprint = request_hash(booking_data)
        await booking_service.hold_idempotency_key(db, customer_id, idempotency_key)
        earlier = await booking_service.get_by_idempotency_key(db, customer_id, idempotency_key)
        if earlier is not None:
            # Already priced, notified and paid for with its coupon: none of that happens twice.
            return replay(earlier, fingerprint, response)
    # Price, shop and duration come from the catalogue, never from the client.
    listing = await lookup_service(booking_data.service_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="Service not found")
    if not listing.get("is_active", False):
        raise HTTPException(status_code=409, detail="Service is not currently offered")
    duration = listing.get("duration_minutes") or booking_data.duration_minutes
    if not duration:
        raise HTTPException(status_code=422, detail="duration_minutes is required for this service")
    # How it is delivered: one of the ways the service offers (older listings: at the shop only).
    mode = booking_data.service_mode
    if mode not in (listing.get("service_modes") or [AT_SHOP]):
        raise HTTPException(status_code=422, detail=f"This service is not offered as {MODE_NAMES[mode]}")
    if mode != AT_SHOP and not booking_data.address_id:
        raise HTTPException(status_code=422, detail=f"Choose the address for {MODE_NAMES[mode]}")
    fee = {AT_HOME: listing.get("home_visit_fee_cents") or 0, PICKUP_DROP: listing.get("pickup_fee_cents") or 0}.get(
        mode, 0
    )
    # Checked before the coupon is used up, and held until the booking is committed (see hold_shop_capacity).
    await _ensure_bookable(db, listing["shop_id"], booking_data.scheduled_at, duration, lookup_schedule, clock())
    price = listing["price_cents"]
    code = (booking_data.coupon_code or "").strip().upper() or None
    if code:
        try:
            price = await price_with_coupon(
                credentials.credentials, customer_id, booking_data.service_id, listing["price_cents"], code
            )
        except CouponRejected as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
    # The coupon applies to the service; the visit or pickup fee is added on top.
    booking_data = booking_data.model_copy(
        update={
            "customer_id": customer_id,
            "shop_id": listing["shop_id"],
            "total_amount": price + fee,
            "duration_minutes": duration,
        }
    )
    meta = {}
    if code:
        meta.update(coupon_code=code, list_price=listing["price_cents"] + fee)
    if fee:
        meta["service_mode_fee"] = fee
    metadata = json.dumps(meta) if meta else None
    try:
        booking = await booking_service.create_booking(
            db, customer_id, booking_data, metadata, idempotency_key, fingerprint
        )
        # Commit first: the background task delays the session's own commit, and the people notified
        # (and the caller's next request) must already see the change.
        await db.commit()
    except IntegrityError:
        # Another request with the same key got there first (without the lock): its booking stands.
        await db.rollback()
        earlier = idempotency_key and await booking_service.get_by_idempotency_key(db, customer_id, idempotency_key)
        if not earlier:
            raise
        log.info("booking_idempotency_race_lost", booking_id=earlier.id)
        return replay(earlier, fingerprint, response)
    background.add_task(
        notify_booking,
        notifier,
        snapshot(booking, listing.get("name")),
        "booking.created",
        customer_id,
        lookup_owner,
        roles=("shop",),
    )
    return booking


async def _ensure_bookable(db, shop_id, start: datetime, duration: int, lookup_schedule, now: datetime) -> None:
    """409 unless the shop is open for the whole booking, it is far enough ahead, and a place is free.

    A shop that has not published opening hours takes any future time, as before hours existed.
    """
    schedule = availability.Schedule.from_shop_service(await lookup_schedule(shop_id) if shop_id else None)
    if not schedule.configured:
        return
    await booking_service.hold_shop_capacity(db, shop_id)
    start = start if start.tzinfo else start.replace(tzinfo=timezone.utc)
    end = start + timedelta(minutes=duration)
    booked = await booking_service.shop_spans(db, shop_id, start, end)
    # The customer picked the time a little while ago; a slot that has just slipped inside the lead time
    # is still taken.
    problem = availability.booking_problem(schedule, start, duration, now, booked, grace=timedelta(minutes=5))
    if problem:
        raise HTTPException(status_code=409, detail=problem)


@router.get("/bookings", response_model=BookingListResponse)
async def list_bookings(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("sub")
    result = await booking_service.list_bookings(db, user_id, page, per_page, status)
    return result


@router.get("/bookings/assigned", response_model=BookingListResponse)
async def list_assigned_bookings(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Jobs assigned to the caller as a provider, newest first."""
    return await booking_service.list_bookings(db, current_user.get("sub"), page, per_page, status, as_provider=True)


@router.get("/bookings/shop/{shop_id}", response_model=BookingListResponse)
async def list_shop_bookings(
    shop_id: str = Depends(require_shop_access),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    provider_id: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await booking_service.list_shop_bookings(
        db, shop_id, page, per_page, status, provider_id=provider_id, date_from=date_from, date_to=date_to
    )


@router.get("/bookings/shop/{shop_id}/summary", response_model=ShopBookingSummary)
async def shop_booking_summary(
    shop_id: str = Depends(require_shop_access),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    date_to = date_to or datetime.now(timezone.utc).date()
    date_from = date_from or date_to - timedelta(days=29)
    if date_from > date_to or (date_to - date_from).days > 366:
        raise HTTPException(status_code=400, detail="Invalid date range (max 366 days)")
    return await booking_service.shop_summary(db, shop_id, date_from, date_to)


@router.get("/bookings/tracking/{provider_id}")
async def can_track_provider(
    provider_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
):
    """Whether the caller may see this provider's live location (used by tracking_service).

    Allowed for the provider, admins, and the customer or shop owner of a booking the provider
    is working on right now. Anyone else gets 404.
    """
    user_id = current_user.get("sub")
    if current_user.get("role") == "admin" or user_id == provider_id:
        return {"allowed": True}
    active = await booking_service.active_bookings_with_provider(db, provider_id)
    if any(b.customer_id == user_id for b in active):
        return {"allowed": True}
    for shop_id in {b.shop_id for b in active if b.shop_id}:
        if await lookup_owner(shop_id) == user_id:
            return {"allowed": True}
    raise HTTPException(status_code=404, detail="No active booking with this provider")


@router.get("/bookings/{booking_id}", response_model=BookingResponse)
async def get_booking(
    booking_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
):
    booking, _ = await _visible_booking(db, booking_id, current_user, lookup_owner)
    return booking


async def _visible_booking(db, booking_id: str, user: dict, lookup_owner):
    """The booking and the caller's relationships to it; 404 for anyone uninvolved."""
    booking = await booking_service.get_booking(db, booking_id)
    parties = await relationships(booking, user, lookup_owner) if booking else set()
    if not parties:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking, parties


async def _authorize_transition(db, booking_id: str, target: str, user: dict, lookup_owner) -> str:
    """Refuses a change the caller may not make; returns the booking's status before it."""
    booking, parties = await _visible_booking(db, booking_id, user, lookup_owner)
    if not may_transition(parties, target):
        raise HTTPException(status_code=403, detail=f"Not allowed to set this booking to {target}")
    return booking.status


def _report_risk_after(background: BackgroundTasks, booking, previous_status: str, actor_id: Optional[str]) -> None:
    signal = risk.booking_signal(booking, previous_status, actor_id)
    if signal:
        background.add_task(risk.report_risk, booking.customer_id, *signal)


@router.put("/bookings/{booking_id}/status", response_model=BookingResponse)
async def update_status(
    booking_id: str,
    update_data: BookingStatusUpdate,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
    notifier: Notifier = Depends(get_notifier),
):
    user_id = current_user.get("sub")
    if update_data.status == BookingStatus.ASSIGNED.value:
        raise HTTPException(status_code=400, detail="Use POST /bookings/{id}/assign to assign a provider")
    previous_status = await _authorize_transition(db, booking_id, update_data.status, current_user, lookup_owner)
    try:
        booking = await booking_service.transition_status(
            db, booking_id, update_data.status, user_id, update_data.reason
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await manager.broadcast(booking_id, {"booking_id": booking_id, "status": booking.status})
    # Commit first: the background task delays the session's own commit, and the people notified
    # (and the caller's next request) must already see the change.
    await db.commit()
    background.add_task(
        notify_booking, notifier, snapshot(booking), f"booking.{booking.status.lower()}", user_id, lookup_owner
    )
    _report_risk_after(background, booking, previous_status, user_id)
    return booking


@router.post("/bookings/{booking_id}/assign", response_model=BookingResponse)
async def assign_provider(
    booking_id: str,
    body: BookingAssignRequest,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
    lookup_staff: Callable[[str, str], Awaitable[set]] = Depends(get_staff_lookup),
    notifier: Notifier = Depends(get_notifier),
):
    """Give a confirmed booking to a provider. Admins (including dispatch) or the booking's shop."""
    booking, parties = await _visible_booking(db, booking_id, current_user, lookup_owner)
    if ADMIN not in parties:
        if SHOP_OWNER not in parties:
            raise HTTPException(status_code=403, detail="Only the shop or an admin can assign a provider")
        # A shop hands its bookings only to its own active staff with a provider account.
        if body.provider_id not in await lookup_staff(booking.shop_id, credentials.credentials):
            raise HTTPException(status_code=422, detail="Provider is not an active staff member of this shop")
    try:
        booking = await booking_service.assign_provider(db, booking_id, body.provider_id, current_user.get("sub"))
    except ProviderUnavailable as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await manager.broadcast(booking_id, {"booking_id": booking_id, "status": booking.status})
    # Commit first: the background task delays the session's own commit, and the people notified
    # (and the caller's next request) must already see the change.
    await db.commit()
    background.add_task(
        notify_booking,
        notifier,
        snapshot(booking),
        "booking.assigned",
        current_user.get("sub"),
        lookup_owner,
        roles=("customer", "provider"),
    )
    return booking


@router.put("/bookings/{booking_id}/ready-by", response_model=BookingResponse)
async def set_ready_by(
    booking_id: str,
    body: BookingReadyByUpdate,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
    notifier: Notifier = Depends(get_notifier),
):
    """When a pickup & drop item should be back with the customer. The shop, its provider or an admin."""
    booking, parties = await _visible_booking(db, booking_id, current_user, lookup_owner)
    if not parties & {ADMIN, SHOP_OWNER, PROVIDER}:
        raise HTTPException(status_code=403, detail="Only the shop or its provider can set the return time")
    try:
        booking = await booking_service.set_ready_by(db, booking, body.ready_by)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    if booking.ready_by is not None:
        background.add_task(
            notify_booking,
            notifier,
            snapshot(booking),
            "booking.ready_by",
            current_user.get("sub"),
            lookup_owner,
            roles=("customer",),
        )
    return booking


@router.post("/bookings/{booking_id}/cancel", response_model=BookingResponse)
async def cancel_booking(
    booking_id: str,
    body: BookingCancelRequest,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
    notifier: Notifier = Depends(get_notifier),
):
    user_id = current_user.get("sub")
    previous_status = await _authorize_transition(
        db, booking_id, BookingStatus.CANCELLED.value, current_user, lookup_owner
    )
    try:
        booking = await booking_service.cancel_booking(db, booking_id, user_id, body.reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await manager.broadcast(booking_id, {"booking_id": booking_id, "status": booking.status})
    # Commit first: the background task delays the session's own commit, and the people notified
    # (and the caller's next request) must already see the change.
    await db.commit()
    background.add_task(notify_booking, notifier, snapshot(booking), "booking.cancelled", user_id, lookup_owner)
    _report_risk_after(background, booking, previous_status, user_id)
    return booking


@router.get("/bookings/{booking_id}/history", response_model=list[BookingStatusHistoryResponse])
async def get_history(
    booking_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
):
    await _visible_booking(db, booking_id, current_user, lookup_owner)
    history = await booking_service.get_booking_history(db, booking_id)
    return history


@router.websocket("/ws/bookings/{booking_id}")
async def booking_websocket(
    booking_id: str,
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
):
    """Live status of a booking, for the people on it (the same ones who may GET it)."""
    # Browsers cannot set headers on a WebSocket handshake, so the access token comes as ?token=.
    try:
        user = verify_access_token(token or "")
    except HTTPException:
        await websocket.close(code=WS_UNAUTHENTICATED)
        return
    booking = await booking_service.get_booking(db, booking_id)
    try:
        parties = await relationships(booking, user, lookup_owner) if booking else set()
    except HTTPException:
        await websocket.close(code=WS_TRY_AGAIN_LATER)  # shop_service is down
        return
    # The socket outlives the request; give its database connection back now.
    await db.close()
    # Unknown and someone else's bookings look the same, as with GET /bookings/{id}.
    if not parties:
        await websocket.close(code=WS_FORBIDDEN)
        return
    if not await manager.connect(booking_id, websocket):
        return
    try:
        while True:
            await websocket.receive_text()
            await websocket.send_json({"type": "pong", "booking_id": booking_id})
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(booking_id, websocket)
