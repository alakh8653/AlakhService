"""WhatsApp through MSG91, with a template WhatsApp has approved.

Business messages started by us must use an approved template, and only reach people who agreed to get them.
The template's text lives in MSG91's panel (docs/WHATSAPP_REPORTS.md); here we fill in its numbered values.
"""

from typing import List, Optional

import httpx
import structlog

log = structlog.get_logger()


class MSG91WhatsAppChannel:
    def __init__(
        self,
        auth_key: str,
        integrated_number: str,
        template: str,
        namespace: str = "",
        language: str = "en",
        api_url: str = "https://api.msg91.com/api/v5/whatsapp/whatsapp-outbound-message/bulk/",
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        self.auth_key = auth_key
        self.integrated_number = integrated_number
        self.template = template
        self.namespace = namespace
        self.language = language
        self.api_url = api_url
        self._transport = transport

    @property
    def configured(self) -> bool:
        return bool(self.auth_key and self.integrated_number and self.template)

    async def send(self, to_number: str, values: List[str]) -> bool:
        if not self.configured:
            return False
        components = {f"body_{i}": {"type": "text", "value": v} for i, v in enumerate(values, start=1)}
        template = {
            "name": self.template,
            "language": {"code": self.language, "policy": "deterministic"},
            "to_and_components": [{"to": [to_number.lstrip("+")], "components": components}],
        }
        if self.namespace:
            template["namespace"] = self.namespace
        payload = {
            "integrated_number": self.integrated_number,
            "content_type": "template",
            "payload": {"messaging_product": "whatsapp", "type": "template", "template": template},
        }
        try:
            async with httpx.AsyncClient(timeout=10.0, transport=self._transport) as client:
                resp = await client.post(self.api_url, json=payload, headers={"authkey": self.auth_key})
        except httpx.HTTPError as e:
            log.error("whatsapp_send_failed", error=str(e))
            return False
        if resp.status_code >= 400:
            log.error("whatsapp_send_rejected", status=resp.status_code)
            return False
        return True
