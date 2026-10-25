"""Tells customers when it is their turn in a queue, through notification_service.

Notifications are sent after the response, best effort: a notification that cannot be delivered is
logged, never a reason to fail the queue change itself.
"""

from typing import Optional

import httpx
import structlog

from app.config import settings

log = structlog.get_logger()


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
