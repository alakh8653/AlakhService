"""The recipient's OWN phone and email, from auth_service, for SMS and email fallbacks.

Used only as the address a message is delivered to. A person's contact details are never written into
a message to anyone else (docs/PRIVACY_AND_CONTACT.md).
"""

from typing import Optional
from urllib.parse import quote

import httpx
import structlog

from app.config import settings

log = structlog.get_logger()


async def fetch_contact(user_id: str, transport: Optional[httpx.AsyncBaseTransport] = None) -> Optional[dict]:
    """{"phone": ..., "email": ...} for an active account, or None (unknown, deleted, or lookup failed)."""
    if not settings.INTERNAL_API_KEY or not user_id:
        return None
    try:
        async with httpx.AsyncClient(base_url=settings.AUTH_SERVICE_URL, timeout=5.0, transport=transport) as client:
            # Dots escaped too: httpx would resolve a ".." segment.
            resp = await client.get(
                f"/internal/users/{quote(user_id, safe='').replace('.', '%2E')}/contact",
                headers={"X-Internal-Key": settings.INTERNAL_API_KEY},
            )
    except httpx.HTTPError as e:
        log.warning("contact_lookup_failed", error=str(e))
        return None
    if resp.status_code != 200:
        if resp.status_code != 404:
            log.warning("contact_lookup_rejected", status=resp.status_code)
        return None
    body = resp.json()
    return {"phone": body.get("phone"), "email": body.get("email")}
