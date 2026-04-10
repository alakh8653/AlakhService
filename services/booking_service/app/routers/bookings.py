from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import structlog

from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.booking import (
    BookingCreate, BookingStatusUpdate, BookingCancelRequest,
    BookingResponse, BookingStatusHistoryResponse, BookingListResponse,
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


@router.get("/bookings/{booking_id}", response_model=BookingResponse)
async def get_booking(
    booking_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    booking = await booking_service.get_booking(db, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking


@router.put("/bookings/{booking_id}/status", response_model=BookingResponse)
async def update_status(
    booking_id: str,
    update_data: BookingStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("sub")
    try:
        booking = await booking_service.transition_status(
            db, booking_id, update_data.status, user_id, update_data.reason
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await manager.broadcast(booking_id, {"booking_id": booking_id, "status": booking.status})
    return booking


@router.post("/bookings/{booking_id}/cancel", response_model=BookingResponse)
async def cancel_booking(
    booking_id: str,
    body: BookingCancelRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("sub")
    try:
        booking = await booking_service.cancel_booking(db, booking_id, user_id, body.reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await manager.broadcast(booking_id, {"booking_id": booking_id, "status": booking.status})
    return booking


@router.get("/bookings/{booking_id}/history", response_model=list[BookingStatusHistoryResponse])
async def get_history(
    booking_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    history = await booking_service.get_booking_history(db, booking_id)
    return history


@router.websocket("/ws/bookings/{booking_id}")
async def booking_websocket(booking_id: str, websocket: WebSocket):
    await manager.connect(booking_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_json({"type": "pong", "booking_id": booking_id})
    except WebSocketDisconnect:
        manager.disconnect(booking_id, websocket)
