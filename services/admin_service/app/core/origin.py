"""Where an admin action came from, for the audit log."""

from dataclasses import dataclass
from typing import Optional

from fastapi import Request

# Long enough for any real browser; a longer header is cut rather than stored whole.
MAX_USER_AGENT = 512
MAX_IP = 64


def clip(value: Optional[str], limit: int) -> Optional[str]:
    return value[:limit] if value else None


@dataclass(frozen=True)
class Origin:
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


def request_origin(request: Request) -> Origin:
    # The gateway overwrites X-Real-IP with the client's address, so a client cannot choose it; a call that
    # skipped the gateway falls back to the connecting peer.
    ip = request.headers.get("x-real-ip") or (request.client.host if request.client else None)
    return Origin(clip(ip, MAX_IP), clip(request.headers.get("user-agent"), MAX_USER_AGENT))
