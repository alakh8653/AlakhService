"""Tells the people on a booking when it changes, through notification_service.

Notifications are sent after the response, best effort: a notification that cannot be delivered is
logged, never a reason to fail the booking change itself.
"""

from datetime import datetime
from typing import Awaitable, Callable, Optional
from zoneinfo import ZoneInfo

import httpx
import structlog

from app.config import settings

log = structlog.get_logger()

OwnerLookup = Callable[[str], Awaitable[Optional[str]]]


class Notifier:
    def __init__(self, base_url: str, key: str, transport: Optional[httpx.AsyncBaseTransport] = None):
        self.base_url = base_url
        self.key = key
        self._transport = transport

    async def send(self, event: str, recipients: list[dict], data: dict) -> None:
        if not self.key or not recipients:
            return
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=5.0, transport=self._transport) as client:
                resp = await client.post(
                    "/internal/notifications/events",
                    json={"event": event, "recipients": recipients, "data": data},
                    headers={"X-Internal-Key": self.key},
                )
            if resp.status_code >= 400:
                log.warning("notify_rejected", notify_event=event, status=resp.status_code)
        except httpx.HTTPError as e:
            log.warning("notify_failed", notify_event=event, error=str(e))


def get_notifier() -> Notifier:
    return Notifier(settings.NOTIFICATION_SERVICE_URL, settings.INTERNAL_API_KEY)


def _when(at: datetime) -> str:
    return at.astimezone(ZoneInfo(settings.DISPLAY_TIMEZONE)).strftime("%d %b, %I:%M %p")


def snapshot(booking, service_name: Optional[str] = None) -> dict:
    """What a notification needs from the booking, taken before the request's session closes."""
    return {
        "booking_id": booking.id,
        "booking_number": booking.booking_number,
        "status": booking.status,
        "customer_id": booking.customer_id,
        "provider_id": booking.provider_id,
        "shop_id": booking.shop_id,
        "scheduled_at": _when(booking.scheduled_at),
        "ready_by": _when(booking.ready_by) if getattr(booking, "ready_by", None) else None,
        "service_name": service_name,
    }


async def notify_booking(
    notifier: Notifier,
    booking: dict,
    event: str,
    actor_id: Optional[str],
    lookup_owner: OwnerLookup,
    roles: tuple[str, ...] = ("customer", "provider", "shop"),
) -> None:
    """Sends [event] to the booking's customer, provider and shop owner (as [roles] allows), except the actor."""
    people = {"customer": booking["customer_id"], "provider": booking["provider_id"]}
    if "shop" in roles and booking["shop_id"]:
        try:
            people["shop"] = await lookup_owner(booking["shop_id"])
        except Exception as e:  # shop_service down: still tell the others
            log.warning("notify_owner_lookup_failed", error=str(e))
    recipients, seen = [], {actor_id}
    for role in roles:
        user_id = people.get(role)
        if user_id and user_id not in seen:
            seen.add(user_id)
            recipients.append({"user_id": user_id, "role": role})
    data = {k: booking[k] for k in ("booking_id", "booking_number", "scheduled_at", "service_name")}
    if booking.get("ready_by"):
        data["ready_by"] = booking["ready_by"]
    await notifier.send(event, recipients, data)
