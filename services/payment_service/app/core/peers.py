"""Calls this service makes to booking_service and shop_service over their /internal routes.

All of them are best effort: payment_service never fails a payment because a peer is down. Each is
a small class so tests can swap in a fake through the FastAPI dependency.
"""

import asyncio
from typing import Optional
from urllib.parse import quote

import httpx
import structlog

from app.config import settings

log = structlog.get_logger()


def _segment(value: str) -> str:
    return quote(value, safe="").replace(".", "%2E")


class BookingSync:
    """Tells booking_service how a booking's payment stands (UNPAID, PAID, REFUNDED, PARTIALLY_REFUNDED)."""

    def __init__(self, base_url: str, key: str, transport: Optional[httpx.AsyncBaseTransport] = None):
        self.base_url = base_url
        self.key = key
        self._transport = transport
        self.retry_delay = 0.5

    async def payment_status(self, booking_id: str, status: str, attempts: int = 3) -> bool:
        if not self.key:
            return False
        for attempt in range(attempts):
            try:
                async with httpx.AsyncClient(base_url=self.base_url, timeout=5.0, transport=self._transport) as client:
                    resp = await client.post(
                        f"/internal/bookings/{_segment(booking_id)}/payment-status",
                        json={"payment_status": status},
                        headers={"X-Internal-Key": self.key},
                    )
                if resp.status_code < 400:
                    return True
                if resp.status_code < 500:  # e.g. the booking does not exist: retrying will not help
                    log.warning("booking_payment_status_rejected", booking_id=booking_id, status=resp.status_code)
                    return False
            except httpx.HTTPError as e:
                log.warning("booking_payment_status_failed", booking_id=booking_id, error=str(e))
            if attempt + 1 < attempts:
                await asyncio.sleep(self.retry_delay * 2**attempt)
        log.error("booking_payment_status_gave_up", booking_id=booking_id, payment_status=status)
        return False


def get_booking_sync() -> BookingSync:
    return BookingSync(settings.BOOKING_SERVICE_URL, settings.INTERNAL_API_KEY)


class ShopDirectory:
    """Shop records and payout details from shop_service's internal routes.

    Returns None when the shop (or the route itself, on an older shop_service) is not there, or when
    shop_service cannot be reached; callers show what they have instead.
    """

    def __init__(self, base_url: str, key: str, transport: Optional[httpx.AsyncBaseTransport] = None):
        self.base_url = base_url
        self.key = key
        self._transport = transport

    async def _get(self, path: str) -> Optional[dict]:
        if not self.key:
            return None
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=5.0, transport=self._transport) as client:
                resp = await client.get(path, headers={"X-Internal-Key": self.key})
        except httpx.HTTPError as e:
            log.warning("shop_service_unreachable", path=path, error=str(e))
            return None
        if resp.status_code != 200:
            if resp.status_code != 404:
                log.warning("shop_service_refused", path=path, status=resp.status_code)
            return None
        try:
            body = resp.json()
        except ValueError:
            return None
        return body if isinstance(body, dict) else None

    async def shop(self, shop_id: str) -> Optional[dict]:
        return await self._get(f"/internal/shops/{_segment(shop_id)}")

    async def payout_details(self, shop_id: str) -> Optional[dict]:
        return await self._get(f"/internal/shops/{_segment(shop_id)}/payout-details")


def get_shop_directory() -> ShopDirectory:
    return ShopDirectory(settings.SHOP_SERVICE_URL, settings.INTERNAL_API_KEY)
