"""Best-effort reports of shop reviews: the admin_service audit log and the owner's notification.

Both are sent after the response; one that cannot be delivered is logged, never a reason to fail the
approval itself.
"""

from dataclasses import dataclass
from typing import Any, Optional

import httpx
import structlog
from fastapi import Request

from app.config import settings

log = structlog.get_logger()

SERVICE = "shop_service"


@dataclass(frozen=True)
class Origin:
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


def request_origin(request: Request) -> Origin:
    # The gateway overwrites X-Real-IP with the client's address, so a client cannot choose it.
    ip = request.headers.get("x-real-ip") or (request.client.host if request.client else None)
    return Origin(ip, request.headers.get("user-agent"))


class Reporter:
    def __init__(
        self,
        admin_url: str,
        notification_url: str,
        key: str,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        self.admin_url = admin_url
        self.notification_url = notification_url
        self.key = key
        self._transport = transport

    async def _post(self, base_url: str, path: str, body: dict, what: str) -> None:
        if not self.key:
            return
        try:
            async with httpx.AsyncClient(base_url=base_url, timeout=5.0, transport=self._transport) as client:
                resp = await client.post(path, json=body, headers={"X-Internal-Key": self.key})
            if resp.status_code >= 400:
                log.warning(f"{what}_rejected", status=resp.status_code)
        except httpx.HTTPError as e:
            log.warning(f"{what}_failed", error=str(e))

    async def audit(
        self,
        admin_id: str,
        action: str,
        shop_id: str,
        origin: Origin,
        old_values: Any = None,
        new_values: Any = None,
    ) -> None:
        await self._post(
            self.admin_url,
            "/internal/audit-logs",
            {
                "admin_id": admin_id,
                "action": action,
                "resource_type": "shop",
                "resource_id": shop_id,
                "old_values": old_values,
                "new_values": new_values,
                "ip_address": origin.ip_address,
                "user_agent": origin.user_agent,
                "service": SERVICE,
            },
            "audit_report",
        )

    async def notify_owner(self, event: str, owner_id: str, data: dict) -> None:
        await self._post(
            self.notification_url,
            "/internal/notifications/events",
            {"event": event, "recipients": [{"user_id": owner_id, "role": "shop"}], "data": data},
            "notify",
        )


def get_reporter() -> Reporter:
    return Reporter(settings.ADMIN_SERVICE_URL, settings.NOTIFICATION_SERVICE_URL, settings.INTERNAL_API_KEY)
