"""SMS through MSG91 (https://msg91.com), with the DLT sender id and template id Indian networks require.

TRAI's DLT rules: every commercial SMS to an Indian number names a registered sender id (header) and
a registered template id, and its text must match that template word for word, with only the
{#var#} parts changed.
"""

from typing import Optional

import httpx
import structlog

log = structlog.get_logger()


class MSG91SMSChannel:
    def __init__(
        self,
        auth_key: str,
        sender_id: str,
        api_url: str = "https://api.msg91.com/api/v2/sendsms",
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        self.auth_key = auth_key
        self.sender_id = sender_id
        self.api_url = api_url
        self._transport = transport

    @property
    def configured(self) -> bool:
        return bool(self.auth_key and self.sender_id)

    async def send(self, to_number: str, body: str, template_id: str) -> bool:
        if not self.configured or not template_id:
            return False
        payload = {
            "sender": self.sender_id,
            "route": "4",  # transactional
            "country": "91",
            "DLT_TE_ID": template_id,
            # MSG91 takes numbers with the country code and no "+".
            "sms": [{"message": body, "to": [to_number.lstrip("+")]}],
        }
        try:
            async with httpx.AsyncClient(timeout=10.0, transport=self._transport) as client:
                resp = await client.post(self.api_url, json=payload, headers={"authkey": self.auth_key})
        except httpx.HTTPError as e:
            log.error("msg91_send_failed", error=str(e))
            return False
        if resp.status_code >= 400:
            log.warning("msg91_rejected", status=resp.status_code, body=resp.text[:200])
            return False
        try:
            # MSG91 answers 200 with {"type": "error"} for some refusals (template mismatch, no balance).
            if resp.json().get("type") == "error":
                log.warning("msg91_rejected", body=resp.text[:200])
                return False
        except ValueError:
            pass
        log.info("sms_sent", provider="msg91", template_id=template_id)
        return True
