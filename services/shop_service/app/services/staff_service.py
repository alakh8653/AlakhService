import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import StaffNotFoundError
from app.models.shop import StaffMember
from app.schemas.hours import DayHours
from app.schemas.shop import StaffCreate, StaffResponse, StaffUpdate


def working_hours(member: StaffMember) -> Optional[List[DayHours]]:
    """Their week, or None when they work the shop's hours."""
    if member.working_hours is None:
        return None
    return [DayHours(**day) for day in json.loads(member.working_hours)]


def _dump_hours(days: Optional[list]) -> Optional[str]:
    if days is None:
        return None
    return json.dumps([d.model_dump() if isinstance(d, DayHours) else d for d in days])


def to_response(member: StaffMember) -> StaffResponse:
    return StaffResponse(
        id=member.id,
        shop_id=member.shop_id,
        user_id=member.user_id,
        name=member.name,
        email=member.email,
        phone=member.phone,
        role=member.role,
        service_ids=json.loads(member.service_ids or "[]"),
        working_hours=working_hours(member),
        is_active=member.is_active,
        created_at=member.created_at,
    )


async def list_staff(db: AsyncSession, shop_id: str, include_inactive: bool = False) -> List[StaffMember]:
    query = select(StaffMember).where(StaffMember.shop_id == shop_id)
    if not include_inactive:
        query = query.where(StaffMember.is_active == True)  # noqa: E712
    return list((await db.execute(query.order_by(StaffMember.name, StaffMember.id))).scalars().all())


async def get_staff(db: AsyncSession, staff_id: str) -> StaffMember:
    member = (await db.execute(select(StaffMember).where(StaffMember.id == staff_id))).scalar_one_or_none()
    if member is None:
        raise StaffNotFoundError()
    return member


async def create_staff(db: AsyncSession, data: StaffCreate) -> StaffMember:
    member = StaffMember(
        id=str(uuid.uuid4()),
        shop_id=data.shop_id,
        user_id=data.user_id,
        name=data.name,
        email=data.email,
        phone=data.phone,
        role=data.role,
        service_ids=json.dumps(sorted(set(data.service_ids))),
        working_hours=_dump_hours(data.working_hours),
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db.add(member)
    await db.flush()
    return member


async def update_staff(db: AsyncSession, member: StaffMember, data: StaffUpdate) -> StaffMember:
    changes = data.model_dump(exclude_unset=True)
    if "service_ids" in changes:
        changes["service_ids"] = json.dumps(sorted(set(changes["service_ids"] or [])))
    if "working_hours" in changes:
        changes["working_hours"] = _dump_hours(data.working_hours)
    for field, value in changes.items():
        setattr(member, field, value)
    await db.flush()
    return member
