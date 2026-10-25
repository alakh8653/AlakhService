"""Records the Terms and Privacy Policy acceptance with compliance_service (the consent register).

Best effort, sent after the response: the version and time are stored on the user row as well,
so a consent that cannot be delivered is logged, never a reason to fail the sign-up.
"""

from typing import Optional

import httpx
import structlog

from app.config import settings

log = structlog.get_logger()

# One record per document accepted, so each can be withdrawn or re-asked separately later.
CONSENT_TYPES = ("terms_of_service", "privacy_policy")


async def record_terms_consent(
    user_id: str,
    version: str,
    ip_address: Optional[str],
    user_agent: Optional[str],
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> None:
    if not settings.INTERNAL_API_KEY or not user_id:
        log.warning("consent_not_recorded", user_id=user_id, reason="internal API not configured")
        return
    try:
        async with httpx.AsyncClient(
            base_url=settings.COMPLIANCE_SERVICE_URL, timeout=5.0, transport=transport
        ) as client:
            for consent_type in CONSENT_TYPES:
                resp = await client.post(
                    "/internal/consent",
                    json={
                        "user_id": user_id,
                        "consent_type": consent_type,
                        "granted": True,
                        "version": version,
                        "ip_address": ip_address,
                        "user_agent": (user_agent or "")[:512] or None,
                    },
                    headers={"X-Internal-Key": settings.INTERNAL_API_KEY},
                )
                if resp.status_code >= 400:
                    log.warning("consent_rejected", user_id=user_id, status=resp.status_code)
                    return
        log.info("consent_recorded", user_id=user_id, version=version)
    except Exception as e:  # the compliance register being down must not break sign-up
        log.warning("consent_failed", user_id=user_id, error=str(e))
