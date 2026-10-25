"""Masked calls: the platform rings both parties of a booking from a virtual number.

A telephony "bridge" (Exotel-style click-to-call) first rings the person who asked for the call, then
connects them to the other party; each sees only the platform's number. Which bridge is used comes from
CALL_PROVIDER: "none" (the default) turns calling off and the apps offer only the chat; "exotel" uses
Exotel's Calls/connect API with the EXOTEL_* settings.

The numbers are looked up from auth_service here, at call time, and go only to the bridge: they are
never stored or returned to anyone.
"""

from dataclasses import dataclass
from typing import Awaitable, Callable, Optional, Protocol

import httpx
import structlog

from app.config import settings
from app.dependencies import path_segment

log = structlog.get_logger()


class CallFailed(Exception):
    """The bridge could not place the call."""


@dataclass
class PlacedCall:
    call_id: Optional[str]
    status: str


class CallBridge(Protocol):
    name: str
    enabled: bool

    async def connect(self, caller_number: str, callee_number: str, reference: str) -> PlacedCall:
        """Ring [caller_number], then connect it to [callee_number]."""


class DisabledBridge:
    name = "none"
    enabled = False

    async def connect(self, caller_number: str, callee_number: str, reference: str) -> PlacedCall:
        raise CallFailed("Calling is not enabled")


class ExotelBridge:
    """Exotel's click-to-call: POST /v1/Accounts/{sid}/Calls/connect rings From, then To, showing CallerId."""

    name = "exotel"
    enabled = True

    def __init__(
        self,
        api_key: str,
        api_token: str,
        account_sid: str,
        caller_id: str,
        subdomain: str = "api.exotel.com",
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        self.api_key = api_key
        self.api_token = api_token
        self.account_sid = account_sid
        self.caller_id = caller_id
        self.base_url = f"https://{subdomain}"
        self._transport = transport

    async def connect(self, caller_number: str, callee_number: str, reference: str) -> PlacedCall:
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                auth=(self.api_key, self.api_token),
                timeout=10.0,
                transport=self._transport,
            ) as client:
                resp = await client.post(
                    f"/v1/Accounts/{path_segment(self.account_sid)}/Calls/connect.json",
                    data={
                        "From": caller_number,
                        "To": callee_number,
                        "CallerId": self.caller_id,
                        "CustomField": reference,
                    },
                )
        except httpx.HTTPError as e:
            raise CallFailed("Telephony provider unreachable") from e
        if resp.status_code >= 400:
            # The body can echo the numbers: log the status only.
            log.warning("call_rejected", provider=self.name, status=resp.status_code)
            raise CallFailed("Telephony provider refused the call")
        call = (resp.json() or {}).get("Call") or {}
        return PlacedCall(call_id=call.get("Sid"), status=(call.get("Status") or "queued").lower())


def bridge_from_settings() -> CallBridge:
    provider = (settings.CALL_PROVIDER or "none").strip().lower()
    if provider == "exotel":
        required = (
            settings.EXOTEL_API_KEY,
            settings.EXOTEL_API_TOKEN,
            settings.EXOTEL_ACCOUNT_SID,
            settings.EXOTEL_CALLER_ID,
        )
        if all(required):
            return ExotelBridge(*required, subdomain=settings.EXOTEL_SUBDOMAIN)
        log.warning("call_provider_misconfigured", provider=provider)
    elif provider not in ("", "none"):
        log.warning("call_provider_unknown", provider=provider)
    return DisabledBridge()


def get_call_bridge() -> CallBridge:
    return bridge_from_settings()


async def fetch_call_number(user_id: str) -> Optional[str]:
    """The number a masked call rings for this user (auth_service), or None if they have none on file."""
    if not settings.INTERNAL_API_KEY:
        return None
    async with httpx.AsyncClient(base_url=settings.AUTH_SERVICE_URL, timeout=5.0) as client:
        try:
            resp = await client.get(
                f"/internal/users/{path_segment(user_id)}/call-contact",
                headers={"X-Internal-Key": settings.INTERNAL_API_KEY},
            )
        except httpx.HTTPError as e:
            raise CallFailed("Auth service unavailable") from e
    if resp.status_code == 404:
        return None
    if resp.status_code != 200:
        raise CallFailed("Auth service unavailable")
    return resp.json().get("phone") or None


NumberLookup = Callable[[str], Awaitable[Optional[str]]]


def get_number_lookup() -> NumberLookup:
    return fetch_call_number
