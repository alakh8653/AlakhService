"""Reports the admin actions this service carries out to admin_service's audit log.

Reports are sent after the response, best effort: an entry that cannot be recorded is logged, never a
reason to fail the action itself.
"""

from dataclasses import dataclass
from typing import Any, Optional

import httpx
import structlog
from fastapi import Request

from app.config import settings

log = structlog.get_logger()

SERVICE = "pricing_engine"


@dataclass(frozen=True)
class Origin:
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


def request_origin(request: Request) -> Origin:
    # The gateway overwrites X-Real-IP with the client's address, so a client cannot choose it; a call that
    # skipped the gateway falls back to the connecting peer.
    ip = request.headers.get("x-real-ip") or (request.client.host if request.client else None)
    return Origin(ip, request.headers.get("user-agent"))


class AuditReporter:
    def __init__(self, base_url: str, key: str, transport: Optional[httpx.AsyncBaseTransport] = None):
        self.base_url = base_url
        self.key = key
        self._transport = transport

    async def record(
        self,
        admin_id: str,
        action: str,
        resource_type: str,
        resource_id: Optional[str],
        origin: Origin,
        old_values: Any = None,
        new_values: Any = None,
    ) -> None:
        if not self.key:
            return
        entry = {
            "admin_id": admin_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "old_values": old_values,
            "new_values": new_values,
            "ip_address": origin.ip_address,
            "user_agent": origin.user_agent,
            "service": SERVICE,
        }
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=5.0, transport=self._transport) as client:
                resp = await client.post("/internal/audit-logs", json=entry, headers={"X-Internal-Key": self.key})
            if resp.status_code >= 400:
                log.warning("audit_report_rejected", action=action, status=resp.status_code)
        except httpx.HTTPError as e:
            log.warning("audit_report_failed", action=action, error=str(e))


def get_audit_reporter() -> AuditReporter:
    return AuditReporter(settings.ADMIN_SERVICE_URL, settings.INTERNAL_API_KEY)
