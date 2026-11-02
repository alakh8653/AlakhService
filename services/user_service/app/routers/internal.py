"""Calls from other platform services (INTERNAL_API_KEY), outside /api/v1 so the gateway never serves them."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.internal import require_internal
from app.database import get_db
from app.models.user import UserAddress

router = APIRouter(dependencies=[Depends(require_internal)])


@router.get("/internal/addresses/{address_id}/location")
async def address_location(address_id: str, db: AsyncSession = Depends(get_db, scope="function")):
    """Where a saved address is (booking_service plans a professional's home visits with it): the city and
    coordinates only, never the street or who lives there."""
    address = await db.get(UserAddress, address_id)
    if address is None:
        raise HTTPException(status_code=404, detail="Address not found")
    return {"latitude": address.latitude, "longitude": address.longitude, "city": address.city}
