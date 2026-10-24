"""Carrying out a dispute's outcome: the money in payment_service, the booking in booking_service.

Both calls are idempotent on the other side (the refund carries the key dispute:{id}; a booking already
in the outcome's status is left alone), so a resolve that failed half way is simply tried again.
"""

from typing import Optional
from urllib.parse import quote

import httpx
import structlog

from app.config import settings

log = structlog.get_logger()

REFUND_FULL, REFUND_PARTIAL, RELEASE_TO_SHOP, NO_ACTION = (
    "REFUND_FULL",
    "REFUND_PARTIAL",
    "RELEASE_TO_SHOP",
    "NO_ACTION",
)
# What the booking becomes: refunded in full, or completed (the shop keeps all or the rest of the money).
BOOKING_OUTCOME = {REFUND_FULL: "REFUNDED", REFUND_PARTIAL: "COMPLETED", RELEASE_TO_SHOP: "COMPLETED"}


class SettlementFailed(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _segment(value: str) -> str:
    return quote(value, safe="").replace(".", "%2E")


class SettlementClient:
    def __init__(
        self,
        payment_url: str,
        booking_url: str,
        key: str,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        self.payment_url = payment_url
        self.booking_url = booking_url
        self.key = key
        self._transport = transport

    async def _post(self, base_url: str, path: str, body: dict, service: str) -> httpx.Response:
        if not self.key:
            raise SettlementFailed(503, "INTERNAL_API_KEY is not set, so the outcome cannot be carried out")
        try:
            async with httpx.AsyncClient(base_url=base_url, timeout=15.0, transport=self._transport) as client:
                return await client.post(path, json=body, headers={"X-Internal-Key": self.key})
        except httpx.HTTPError as e:
            log.warning("dispute_settlement_unreachable", service=service, error=str(e))
            raise SettlementFailed(502, f"{service} could not be reached; nothing was resolved, try again") from e

    @staticmethod
    def _detail(resp: httpx.Response) -> str:
        try:
            return str(resp.json().get("detail") or resp.text[:200])
        except ValueError:
            return resp.text[:200]

    async def settle_money(self, dispute_id: str, booking_id: str, outcome: str, amount_cents: Optional[int]) -> dict:
        base = f"/internal/payments/booking/{_segment(booking_id)}"
        if outcome == RELEASE_TO_SHOP:
            resp = await self._post(self.payment_url, f"{base}/release", {}, "payment_service")
        else:
            body = {
                "amount_cents": amount_cents if outcome == REFUND_PARTIAL else None,
                "reason": f"Dispute {dispute_id} resolved",
                "idempotency_key": f"dispute:{dispute_id}",
            }
            resp = await self._post(self.payment_url, f"{base}/refund", body, "payment_service")
        if resp.status_code >= 400:
            # 409/422 explain themselves (no payment to refund, too much); anything else is an outage.
            code = resp.status_code if resp.status_code in (409, 422) else 502
            raise SettlementFailed(code, f"Payment: {self._detail(resp)}")
        return resp.json()

    async def settle_booking(self, booking_id: str, outcome: str) -> Optional[dict]:
        resp = await self._post(
            self.booking_url,
            f"/internal/bookings/{_segment(booking_id)}/resolve-dispute",
            {"outcome": BOOKING_OUTCOME[outcome]},
            "booking_service",
        )
        if resp.status_code == 409:  # the booking itself was never marked DISPUTED: nothing to change there
            log.info("dispute_booking_not_disputed", booking_id=booking_id, detail=self._detail(resp))
            return None
        if resp.status_code >= 400:
            raise SettlementFailed(502, f"Booking: {self._detail(resp)}")
        return resp.json()


def get_settlement_client() -> SettlementClient:
    return SettlementClient(settings.PAYMENT_SERVICE_URL, settings.BOOKING_SERVICE_URL, settings.INTERNAL_API_KEY)
