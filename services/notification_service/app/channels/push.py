"""Push notifications through Firebase Cloud Messaging's HTTP v1 API.

FCM authenticates with a service account: a short-lived OAuth token is obtained by signing a JWT
with the account's private key. (The legacy server-key API was shut down by Google in 2024.)
"""

import json
import time
from typing import Optional

import httpx
import structlog
from jose import jwt

log = structlog.get_logger()

SCOPE = "https://www.googleapis.com/auth/firebase.messaging"


class FCMChannel:
    def __init__(self, service_account: Optional[dict], transport: Optional[httpx.AsyncBaseTransport] = None):
        self.account = service_account
        self._transport = transport
        self._token: Optional[str] = None
        self._token_expires = 0.0

    @classmethod
    def from_settings(cls, service_account_json: str, service_account_file: str) -> "FCMChannel":
        raw = service_account_json
        if not raw and service_account_file:
            try:
                with open(service_account_file) as f:
                    raw = f.read()
            except OSError as e:
                log.error("fcm_service_account_unreadable", error=str(e))
        return cls(json.loads(raw) if raw else None)

    @property
    def configured(self) -> bool:
        return bool(self.account)

    async def _access_token(self, client: httpx.AsyncClient) -> str:
        if self._token and time.time() < self._token_expires - 60:
            return self._token
        now = int(time.time())
        token_uri = self.account.get("token_uri", "https://oauth2.googleapis.com/token")
        assertion = jwt.encode(
            {"iss": self.account["client_email"], "scope": SCOPE, "aud": token_uri, "iat": now, "exp": now + 3600},
            self.account["private_key"],
            algorithm="RS256",
        )
        resp = await client.post(
            token_uri,
            data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion},
        )
        resp.raise_for_status()
        body = resp.json()
        self._token = body["access_token"]
        self._token_expires = now + int(body.get("expires_in", 3600))
        return self._token

    async def send(self, device_token: str, title: str, body: str, data: Optional[dict] = None) -> bool:
        if not self.configured:
            return False
        url = f"https://fcm.googleapis.com/v1/projects/{self.account['project_id']}/messages:send"
        message = {
            "message": {
                "token": device_token,
                "notification": {"title": title, "body": body},
                # FCM data values must be strings.
                "data": {k: str(v) for k, v in (data or {}).items() if v is not None},
            }
        }
        try:
            async with httpx.AsyncClient(timeout=10, transport=self._transport) as client:
                token = await self._access_token(client)
                resp = await client.post(url, json=message, headers={"Authorization": f"Bearer {token}"})
        except Exception as e:
            log.error("fcm_send_failed", error=str(e))
            return False
        if resp.status_code != 200:
            log.warning("fcm_rejected", status=resp.status_code, body=resp.text[:200])
            return False
        return True
