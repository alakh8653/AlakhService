"""Spends a customer's loyalty points on a booking being made (payment_service keeps the points).

Best effort: if payment_service cannot be reached the booking is made at its normal price (the
response shows no points were used), never refused.
"""

from typing import Optional

import httpx
import structlog

from app.config import settings

log = structlog.get_logger()


class PointsWallet:
    def __init__(self, base_url: str, transport: Optional[httpx.AsyncBaseTransport] = None):
        self.base_url = base_url
        self._transport = transport

    async def _post(self, path: str, body: dict) -> Optional[dict]:
        if not settings.INTERNAL_API_KEY:
            return None
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=5.0, transport=self._transport) as client:
                resp = await client.post(path, json=body, headers={"X-Internal-Key": settings.INTERNAL_API_KEY})
            if resp.status_code >= 400:
                log.warning("points_rejected", path=path, status=resp.status_code)
                return None
            return resp.json()
        except httpx.HTTPError as e:
            log.warning("points_unreachable", path=path, error=str(e))
            return None

    async def redeem(self, customer_id: str, booking_id: str, price_cents: int) -> int:
        """The discount the customer's points give on [price_cents] (0 if they have none, or on failure)."""
        answer = await self._post(
            "/internal/payments/loyalty/redeem",
            {"customer_id": customer_id, "booking_id": booking_id, "price_cents": price_cents},
        )
        return int((answer or {}).get("discount_cents") or 0)

    async def release(self, booking_id: str) -> None:
        """Gives the points back for a booking that was not made after all."""
        await self._post("/internal/payments/loyalty/release", {"booking_id": booking_id})


def get_points_wallet() -> PointsWallet:
    return PointsWallet(settings.PAYMENT_SERVICE_URL)
