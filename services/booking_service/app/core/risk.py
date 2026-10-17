"""Reports what customers do with their bookings to trust_risk_service.

Best effort, sent after the response: a signal that cannot be delivered is logged, never a reason to
fail the booking change itself.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import httpx
import structlog

from app.config import settings
from app.core.fsm import BookingStatus
from app.dependencies import path_segment

log = structlog.get_logger()

# Cancelling closer to the appointment than this leaves the shop with a slot it cannot refill.
LATE_CANCELLATION_WINDOW = timedelta(hours=2)

Signal = Tuple[str, float, bool]  # signal_type, value, is_risk_event


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
            resp = await client.post(
                f"/internal/risk/{path_segment(user_id)}/signals",
                json={"signal_type": signal_type, "value": value, "is_risk_event": is_risk_event},
                headers={"X-Internal-Key": settings.INTERNAL_API_KEY},
            )
        if resp.status_code >= 400:
            log.warning("risk_signal_rejected", signal_type=signal_type, status=resp.status_code)
    except Exception as e:  # never let trust scoring break the action that triggered it
        log.warning("risk_signal_failed", signal_type=signal_type, error=str(e))


def booking_signal(
    booking, previous_status: str, actor_id: Optional[str], now: Optional[datetime] = None
) -> Optional[Signal]:
    """What a status change says about the booking's customer, if anything."""
    if booking.status == BookingStatus.CANCELLED.value and actor_id == booking.customer_id:
        scheduled = (
            booking.scheduled_at if booking.scheduled_at.tzinfo else booking.scheduled_at.replace(tzinfo=timezone.utc)
        )
        if (now or datetime.now(timezone.utc)) > scheduled - LATE_CANCELLATION_WINDOW:
            return ("late_cancellation", 0.4, True)
    # A dispute resolved back to COMPLETED was already counted when the booking first completed.
    if booking.status == BookingStatus.COMPLETED.value and previous_status != BookingStatus.DISPUTED.value:
        return ("booking_completed", 0.0, False)
    return None
