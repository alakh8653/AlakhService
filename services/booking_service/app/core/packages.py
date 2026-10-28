"""Uses a visit of the customer's prepaid package for a booking being made (payment_service keeps packages).

Unlike points, a package the booking cannot use refuses the booking: the customer expects it to cost
nothing more, so it is never made at the normal price instead.
"""

from typing import Optional

import httpx
import structlog

from app.config import settings

log = structlog.get_logger()


class PackageUnusable(Exception):
    """The package cannot be used for this booking; carries the status and reason to answer with."""

    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


class PackageWallet:
    def __init__(self, base_url: str, transport: Optional[httpx.AsyncBaseTransport] = None):
        self.base_url = base_url
        self._transport = transport

    async def _post(self, path: str, body: dict) -> httpx.Response:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=5.0, transport=self._transport) as client:
            return await client.post(path, json=body, headers={"X-Internal-Key": settings.INTERNAL_API_KEY})

    async def redeem(self, customer_id: str, purchase_id: str, service_id: str, booking_id: str) -> int:
        """Uses one visit for [booking_id]; returns its share of the package price, or raises PackageUnusable."""
        body = {
            "customer_id": customer_id,
            "purchase_id": purchase_id,
            "service_id": service_id,
            "booking_id": booking_id,
        }
        try:
            resp = await self._post("/internal/payments/packages/redeem", body)
        except httpx.HTTPError as e:
            log.warning("package_unreachable", error=str(e))
            raise PackageUnusable(503, "Packages cannot be used right now. Please try again.") from e
        if resp.status_code >= 500 or resp.status_code in (401, 403):
            raise PackageUnusable(503, "Packages cannot be used right now. Please try again.")
        if resp.status_code >= 400:
            raise PackageUnusable(resp.status_code, resp.json().get("detail") or "This package cannot be used")
        return int(resp.json().get("visit_value_cents") or 0)

    async def release(self, booking_id: str) -> None:
        """Gives the visit back for a booking that was not made after all (best effort)."""
        try:
            await self._post("/internal/payments/packages/release", {"booking_id": booking_id})
        except httpx.HTTPError as e:
            log.warning("package_release_failed", booking_id=booking_id, error=str(e))


def get_package_wallet() -> PackageWallet:
    return PackageWallet(settings.PAYMENT_SERVICE_URL)
