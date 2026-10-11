"""Razorpay: creating checkout orders and checking the signatures Razorpay puts on its callbacks."""

import hashlib
import hmac
from typing import Optional

import httpx

from app.config import settings

API_URL = "https://api.razorpay.com/v1"


class GatewayError(Exception):
    """Razorpay could not be reached or refused the request."""


def _signature_matches(secret: str, message: bytes, signature: str) -> bool:
    expected = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


class RazorpayGateway:
    def __init__(
        self,
        key_id: Optional[str] = None,
        key_secret: Optional[str] = None,
        webhook_secret: Optional[str] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        self.key_id = key_id
        self.key_secret = key_secret
        self.webhook_secret = webhook_secret
        self._transport = transport

    @property
    def configured(self) -> bool:
        return bool(self.key_id and self.key_secret)

    async def create_order(self, amount_cents: int, currency: str, receipt: str, notes: dict) -> str:
        """Creates an order for the checkout to pay and returns its id."""
        try:
            async with httpx.AsyncClient(timeout=10.0, transport=self._transport) as client:
                resp = await client.post(
                    f"{API_URL}/orders",
                    auth=(self.key_id, self.key_secret),
                    json={"amount": amount_cents, "currency": currency, "receipt": receipt[:40], "notes": notes},
                )
        except httpx.HTTPError as e:
            raise GatewayError(f"Razorpay unreachable: {e}") from e
        if resp.status_code >= 400:
            raise GatewayError(f"Razorpay refused the order ({resp.status_code})")
        return resp.json()["id"]

    def checkout_signature_valid(self, order_id: str, payment_id: str, signature: str) -> bool:
        """The signature Razorpay's checkout returns to the app after a successful payment."""
        if not self.key_secret:
            return False
        return _signature_matches(self.key_secret, f"{order_id}|{payment_id}".encode(), signature)

    def webhook_signature_valid(self, body: bytes, signature: str) -> bool:
        """X-Razorpay-Signature: an HMAC of the raw request body with the webhook secret."""
        if not self.webhook_secret:
            return False
        return _signature_matches(self.webhook_secret, body, signature)


def get_razorpay() -> RazorpayGateway:
    return RazorpayGateway(
        key_id=settings.RAZORPAY_KEY_ID,
        key_secret=settings.RAZORPAY_KEY_SECRET,
        webhook_secret=settings.RAZORPAY_WEBHOOK_SECRET,
    )
