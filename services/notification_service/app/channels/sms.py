import structlog
from typing import Optional

log = structlog.get_logger()

class TwilioSMSChannel:
    def __init__(self, account_sid: str, auth_token: str, from_number: str):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number
        self._client = None

    def _get_client(self):
        if self._client is None:
            from twilio.rest import Client
            self._client = Client(self.account_sid, self.auth_token)
        return self._client

    async def send(self, to_number: str, body: str) -> bool:
        import asyncio
        try:
            client = self._get_client()
            loop = asyncio.get_event_loop()
            message = await loop.run_in_executor(
                None,
                lambda: client.messages.create(
                    body=body,
                    from_=self.from_number,
                    to=to_number,
                ),
            )
            log.info("sms_sent", sid=message.sid, to=to_number)
            return True
        except Exception as e:
            log.error("sms_send_failed", error=str(e), to=to_number)
            return False
