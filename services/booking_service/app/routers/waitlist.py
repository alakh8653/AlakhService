"""The customer's waitlist for full days (see app.core.waitlist)."""

from datetime import date
from typing import Awaitable, Callable, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import waitlist
from app.database import get_db
from app.dependencies import get_current_user, get_service_lookup
from app.models.waitlist import WaitlistEntry

router = APIRouter()


class WaitlistJoin(BaseModel):
    service_id: str = Field(min_length=1, max_length=128)
    day: date = Field(alias="date")


class WaitlistOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    service_id: str
    shop_id: str
    day: date = Field(serialization_alias="date")


@router.post("/waitlist", response_model=WaitlistOut, response_model_by_alias=True, status_code=201)
async def join_waitlist(
    body: WaitlistJoin,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    lookup_service: Callable[[str], Awaitable[Optional[dict]]] = Depends(get_service_lookup),
):
    """Tells the customer once if a time opens up at the service's shop on that day."""
    listing = await lookup_service(body.service_id)
    if listing is None or not listing.get("shop_id"):
        raise HTTPException(status_code=404, detail="Service not found")
    try:
        entry = await waitlist.join(db, current_user["sub"], body.service_id, listing["shop_id"], body.day)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return entry


@router.get("/waitlist", response_model=List[WaitlistOut], response_model_by_alias=True)
async def my_waitlist(db: AsyncSession = Depends(get_db), current_user: dict = Depends(get_current_user)):
    return await waitlist.waiting(db, current_user["sub"])


@router.delete("/waitlist/{entry_id}", status_code=204)
async def leave_waitlist(
    entry_id: str, db: AsyncSession = Depends(get_db), current_user: dict = Depends(get_current_user)
):
    entry = await db.get(WaitlistEntry, entry_id)
    if entry is None or entry.customer_id != current_user["sub"]:
        raise HTTPException(status_code=404, detail="Not on the waitlist")
    await db.delete(entry)
    await db.flush()
    return Response(status_code=204)
