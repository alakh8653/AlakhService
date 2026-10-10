"""Who may see a booking and which status changes each party may make.

A caller relates to a booking as its customer, its assigned provider, the
owner of its shop, or an admin. Anyone else is told the booking does not
exist. The state machine (app/core/fsm.py) still decides which transitions
are valid at all; this only decides who may request them.
"""
from typing import Awaitable, Callable, Optional, Set

from app.core.fsm import BookingStatus
from app.models.booking import Booking

ADMIN = "admin"
CUSTOMER = "customer"
PROVIDER = "provider"
SHOP_OWNER = "shop_owner"

# Target statuses each party may move a booking to. Refunds and resolving a
# dispute back to COMPLETED are left to admins (dispute/payment workflows).
ALLOWED_TARGETS = {
    CUSTOMER: {BookingStatus.CANCELLED, BookingStatus.DISPUTED},
    PROVIDER: {
        BookingStatus.PROVIDER_EN_ROUTE,
        BookingStatus.IN_PROGRESS,
        BookingStatus.COMPLETED,
    },
    SHOP_OWNER: {
        BookingStatus.CONFIRMED,
        BookingStatus.ASSIGNED,
        BookingStatus.PROVIDER_EN_ROUTE,
        BookingStatus.IN_PROGRESS,
        BookingStatus.COMPLETED,
        BookingStatus.CANCELLED,
    },
}

OwnerLookup = Callable[[str], Awaitable[Optional[str]]]


async def relationships(booking: Booking, user: dict, lookup_owner: OwnerLookup) -> Set[str]:
    """Every capacity in which `user` is involved with `booking` (empty if none)."""
    user_id = user.get("sub")
    found: Set[str] = set()
    if user.get("role") == ADMIN:
        found.add(ADMIN)
    if booking.customer_id == user_id:
        found.add(CUSTOMER)
    if booking.provider_id and booking.provider_id == user_id:
        found.add(PROVIDER)
    if booking.shop_id and not found & {ADMIN}:
        if await lookup_owner(booking.shop_id) == user_id:
            found.add(SHOP_OWNER)
    return found


def may_transition(parties: Set[str], target: str) -> bool:
    if ADMIN in parties:
        return True
    try:
        status = BookingStatus(target)
    except ValueError:
        return False
    return any(status in ALLOWED_TARGETS.get(party, set()) for party in parties)
