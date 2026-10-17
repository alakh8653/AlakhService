"""Reports customers who were called and never turned up to trust_risk_service.

Best effort, sent after the response: a signal that cannot be delivered is logged, never a reason to
fail the queue change itself.
"""

from typing import Optional
from urllib.parse import quote

import httpx
import structlog

from app.config import settings

log = structlog.get_logger()

NO_SHOW = ("no_show", 0.5, True)  # signal_type, value, is_risk_event


async def report_risk(
    user_id: str,
    signal_type: str,
    value: float,
    is_risk_event: bool,
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> None:
    if not settings.INTERNAL_API_KEY or not user_id:
        return
    try:
        async with httpx.AsyncClient(
            base_url=settings.TRUST_RISK_SERVICE_URL, timeout=5.0, transport=transport
        ) as client:
            # Dots escaped too: httpx would resolve a ".." segment.
            resp = await client.post(
                f"/internal/risk/{quote(user_id, safe='').replace('.', '%2E')}/signals",
                json={"signal_type": signal_type, "value": value, "is_risk_event": is_risk_event},
                headers={"X-Internal-Key": settings.INTERNAL_API_KEY},
            )
        if resp.status_code >= 400:
            log.warning("risk_signal_rejected", signal_type=signal_type, status=resp.status_code)
    except Exception as e:  # never let trust scoring break the action that triggered it
        log.warning("risk_signal_failed", signal_type=signal_type, error=str(e))
