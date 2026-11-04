"""What each side of a booking is shown of the other, so contact stays on the platform.

A shop (its owner and the provider doing the job) sees the customer as a display name ("Ravi S."),
never their phone, email or full name; free text the customer wrote has contact details hidden; and
the customer's saved address only for a home visit or pickup, while the booking is still open.
The customer and admins see the booking as it is, except that the customer gets the reason a booking was
cancelled with contact details hidden too: the shop wrote it.
"""

from typing import Iterable, List, Optional

from app.core.contact_filter import mask_contact
from app.core.fsm import AT_SHOP, BookingStatus
from app.core.names import FALLBACK, NameLookup
from app.schemas.booking import BookingResponse, BookingStatusHistoryResponse

# After these the job is over: nobody needs to go to the customer's address any more.
CLOSED_STATUSES = {
    BookingStatus.COMPLETED.value,
    BookingStatus.CANCELLED.value,
    BookingStatus.REFUNDED.value,
    BookingStatus.DISPUTED.value,
}


def sees_everything(booking, user: dict) -> bool:
    return user.get("role") == "admin" or booking.customer_id == user.get("sub")


def masked(text: Optional[str]) -> Optional[str]:
    return mask_contact(text).text if text else text


def shape(booking, user: dict, display_name: str) -> BookingResponse:
    out = BookingResponse.model_validate(booking).model_copy(update={"customer_display_name": display_name})
    if user.get("role") != "admin":
        out = out.model_copy(update={"cancellation_reason": masked(out.cancellation_reason)})
    if booking.status in CLOSED_STATUSES:  # a request left unanswered ends with the booking
        out = out.model_copy(
            update={"pending_extra_id": None, "pending_extra_amount": None, "pending_extra_reason": None}
        )
    if sees_everything(booking, user):
        return out
    hidden = {"notes": masked(out.notes), "item_description": masked(out.item_description)}
    if booking.service_mode == AT_SHOP or booking.status in CLOSED_STATUSES:
        hidden["address_id"] = None
    return out.model_copy(update=hidden)


async def present(booking, user: dict, lookup_names: NameLookup) -> BookingResponse:
    return (await present_many([booking], user, lookup_names))[0]


async def present_many(bookings: Iterable, user: dict, lookup_names: NameLookup) -> List[BookingResponse]:
    bookings = list(bookings)
    try:
        names = await lookup_names({b.customer_id for b in bookings})
    except Exception:  # never refuse a booking list for want of a name
        names = {}
    return [shape(b, user, names.get(b.customer_id, FALLBACK)) for b in bookings]


async def present_page(page: dict, user: dict, lookup_names: NameLookup) -> dict:
    return {**page, "items": await present_many(page["items"], user, lookup_names)}


def present_history(entries: Iterable, booking, user: dict) -> List[BookingStatusHistoryResponse]:
    """Reasons are free text either side wrote ("cancelled, call me on ..."): contact details are hidden."""
    out = [BookingStatusHistoryResponse.model_validate(e) for e in entries]
    if user.get("role") == "admin":
        return out
    return [e.model_copy(update={"reason": masked(e.reason)}) for e in out]
