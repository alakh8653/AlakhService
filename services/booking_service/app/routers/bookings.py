from datetime import date, datetime, timedelta, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import OwnerLookup, may_transition, relationships
from app.core.fsm import BookingStatus
from app.database import get_db
from app.dependencies import get_current_user, get_shop_owner_lookup, require_shop_access
from app.schemas.booking import (
    BookingCancelRequest,
    BookingCreate,
    BookingListResponse,
    BookingResponse,
    BookingStatusHistoryResponse,
    BookingStatusUpdate,
    ShopBookingSummary,
)
from app.services.booking_service import booking_service

router = APIRouter()
log = structlog.get_logger()


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, booking_id: str, websocket: WebSocket):
        await websocket.accept()
        if booking_id not in self.active_connections:
            self.active_connections[booking_id] = []
        self.active_connections[booking_id].append(websocket)

    def disconnect(self, booking_id: str, websocket: WebSocket):
        if booking_id in self.active_connections:
            try:
                self.active_connections[booking_id].remove(websocket)
            except ValueError:
                pass

    async def broadcast(self, booking_id: str, data: dict):
        if booking_id in self.active_connections:
            dead = []
            for ws in self.active_connections[booking_id]:
                try:
                    await ws.send_json(data)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                try:
                    self.active_connections[booking_id].remove(ws)
                except ValueError:
                    pass


manager = ConnectionManager()


@router.post("/bookings", response_model=BookingResponse, status_code=201)
async def create_booking(
    booking_data: BookingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    customer_id = current_user.get("sub")
    booking = await booking_service.create_booking(db, customer_id, booking_data)
    return booking


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


async def _authorize_transition(db, booking_id: str, target: str, user: dict, lookup_owner) -> None:
    _, parties = await _visible_booking(db, booking_id, user, lookup_owner)
    if not may_transition(parties, target):
        raise HTTPException(status_code=403, detail=f"Not allowed to set this booking to {target}")


@router.put("/bookings/{booking_id}/status", response_model=BookingResponse)
async def update_status(
    booking_id: str,
    update_data: BookingStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
):
    user_id = current_user.get("sub")
    await _authorize_transition(db, booking_id, update_data.status, current_user, lookup_owner)
    try:
        booking = await booking_service.transition_status(
            db, booking_id, update_data.status, user_id, update_data.reason
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await manager.broadcast(booking_id, {"booking_id": booking_id, "status": booking.status})
    return booking


@router.post("/bookings/{booking_id}/cancel", response_model=BookingResponse)
async def cancel_booking(
    booking_id: str,
    body: BookingCancelRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    lookup_owner: OwnerLookup = Depends(get_shop_owner_lookup),
):
    user_id = current_user.get("sub")
    await _authorize_transition(db, booking_id, BookingStatus.CANCELLED.value, current_user, lookup_owner)
    try:
        booking = await booking_service.cancel_booking(db, booking_id, user_id, body.reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await manager.broadcast(booking_id, {"booking_id": booking_id, "status": booking.status})
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
async def booking_websocket(booking_id: str, websocket: WebSocket):
    await manager.connect(booking_id, websocket)
    try:
        while True:
            await websocket.receive_text()
            await websocket.send_json({"type": "pong", "booking_id": booking_id})
    except WebSocketDisconnect:
        manager.disconnect(booking_id, websocket)
