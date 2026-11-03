"""Caller identity from the bearer access token.

Tokens are verified here rather than trusting gateway-set headers, because the service port can
be reached without going through the gateway.
"""

from dataclasses import dataclass
from typing import Awaitable, Callable, Optional
from urllib.parse import quote

import httpx
import structlog
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import settings

bearer = HTTPBearer(auto_error=False)
log = structlog.get_logger()


def path_segment(value: str) -> str:
    """A client-supplied id as exactly one URL path segment of an internal call.

    quote() leaves "." alone and httpx resolves "..", so dots are escaped too.
    """
    return quote(value, safe="").replace(".", "%2E")


@dataclass(frozen=True)
class Caller:
    user_id: str
    role: str
    token: str = ""

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def _caller_from_token(token: str) -> Caller:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from None
    # Refresh and single-purpose (e.g. password reset) tokens share the signing key; reject them.
    if not payload.get("sub") or payload.get("type") != "access" or "purpose" in payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return Caller(payload["sub"], payload.get("role") or "user", token)


def require_caller(credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer)) -> Caller:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return _caller_from_token(credentials.credentials)


def optional_caller(credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer)) -> Optional[Caller]:
    """The signed-in caller on a public endpoint, or None for someone who sent no token.

    A token that is sent but expired or invalid is a 401, not an anonymous visit: as a visitor, an owner
    would be told their shop in review does not exist, and their app would have no reason to renew the
    token and ask again.
    """
    if credentials is None:
        return None
    return _caller_from_token(credentials.credentials)


def ensure_owner(owner_id: str, caller: Caller) -> None:
    if not caller.is_admin and caller.user_id != owner_id:
        raise HTTPException(status_code=403, detail="Not your shop")


async def fetch_booking(booking_id: str, caller: Caller) -> Optional[dict]:
    """The booking as booking_service shows it to the caller, or None if they may not see it."""
    async with httpx.AsyncClient(base_url=settings.BOOKING_SERVICE_URL, timeout=5.0) as client:
        try:
            resp = await client.get(
                f"/api/v1/bookings/{path_segment(booking_id)}", headers={"Authorization": f"Bearer {caller.token}"}
            )
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=503, detail="Booking service unavailable") from exc
    if resp.status_code in (403, 404):
        return None
    if resp.status_code != 200:
        raise HTTPException(status_code=503, detail="Booking service unavailable")
    return resp.json()


async def cancel_shop_bookings(shop_id: str, because: str = "removed") -> None:
    """Has booking_service cancel and refund what has not started at this shop. Raises when it refuses
    (removing a shop while a booking is being served) or cannot be reached: then the shop must stay as it is."""
    if not settings.INTERNAL_API_KEY:
        return
    async with httpx.AsyncClient(base_url=settings.BOOKING_SERVICE_URL, timeout=30.0) as client:
        try:
            resp = await client.post(
                f"/internal/bookings/shops/{path_segment(shop_id)}/cancel-upcoming",
                params={"because": because},
                headers={"X-Internal-Key": settings.INTERNAL_API_KEY},
            )
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=503, detail="Booking service unavailable") from exc
    if resp.status_code == 409:
        raise HTTPException(status_code=409, detail=resp.json().get("detail", "Bookings are being served"))
    if resp.status_code != 200:
        raise HTTPException(status_code=503, detail="Booking service unavailable")


ShopBookingCanceller = Callable[..., Awaitable[None]]


def get_shop_booking_canceller() -> ShopBookingCanceller:
    return cancel_shop_bookings


async def cancel_bookings_made_meanwhile(
    cancel_bookings: ShopBookingCanceller, shop_id: str, because: str = "removed"
) -> None:
    """The second pass, once the shop is closed. The shop's fate is already decided, so a failure is only logged."""
    try:
        await cancel_bookings(shop_id, because)
    except HTTPException as e:
        log.warning("shop_closed_second_cancel_failed", shop_id=shop_id, because=because, detail=e.detail)


BookingLookup = Callable[[str, Caller], Awaitable[Optional[dict]]]


def get_booking_lookup() -> BookingLookup:
    return fetch_booking


def public_name(full_name: Optional[str]) -> Optional[str]:
    """First name and last initial: "priya ravi sharma" -> "Priya S.".

    Anything that looks like a contact detail rather than a name (an email or a number) is dropped.
    """
    parts = (full_name or "").split()
    if not parts or any("@" in p or any(c.isdigit() for c in p) for p in parts):
        return None
    first = parts[0][:30]
    first = first[0].upper() + first[1:]
    return f"{first} {parts[-1][0].upper()}." if len(parts) > 1 else first


async def fetch_display_name(caller: Caller) -> Optional[str]:
    """The caller's public reviewer name, or None when their account can't be read.

    A review is never refused for this; it is shown as from a verified customer instead.
    """
    async with httpx.AsyncClient(base_url=settings.AUTH_SERVICE_URL, timeout=5.0) as client:
        try:
            resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {caller.token}"})
        except httpx.HTTPError:
            return None
    if resp.status_code != 200:
        return None
    return public_name(resp.json().get("full_name"))


NameLookup = Callable[[Caller], Awaitable[Optional[str]]]


def get_name_lookup() -> NameLookup:
    return fetch_display_name
