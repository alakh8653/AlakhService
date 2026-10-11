"""Tells the payer and the shop about payments, through notification_service.

Notifications are sent after the response, best effort: a notification that cannot be delivered is
logged, never a reason to fail the payment itself.
"""

from typing import Optional

import httpx
import structlog

from app.config import settings

log = structlog.get_logger()


class Notifier:
    def __init__(self, base_url: str, key: str, transport: Optional[httpx.AsyncBaseTransport] = None):
        self.base_url = base_url
        self.key = key
        self._transport = transport

    async def send(self, event: str, recipients: list[dict], data: dict) -> None:
        if not self.key or not recipients:
            return
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=5.0, transport=self._transport) as client:
                resp = await client.post(
                    "/internal/notifications/events",
                    json={"event": event, "recipients": recipients, "data": data},
                    headers={"X-Internal-Key": self.key},
                )
            if resp.status_code >= 400:
                log.warning("notify_rejected", notify_event=event, status=resp.status_code)
        except httpx.HTTPError as e:
            log.warning("notify_failed", notify_event=event, error=str(e))


def get_notifier() -> Notifier:
    return Notifier(settings.NOTIFICATION_SERVICE_URL, settings.INTERNAL_API_KEY)


async def notify_payment(notifier: Notifier, event: str, payment: dict) -> None:
    """payment.completed reaches the payer and the payee; payment.failed only the payer."""
    recipients = [{"user_id": payment["payer_id"], "role": "customer"}]
    if event == "payment.completed" and payment["payee_id"] != payment["payer_id"]:
        recipients.append({"user_id": payment["payee_id"], "role": "shop"})
    await notifier.send(event, recipients, {
        "payment_id": payment["id"],
        "booking_id": payment["booking_id"],
        "amount": f"{payment['amount_cents'] / 100:.2f}",
    })


def payment_snapshot(payment) -> dict:
    return {k: getattr(payment, k) for k in ("id", "booking_id", "payer_id", "payee_id", "amount_cents")}
