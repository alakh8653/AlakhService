"""Caller identity from the bearer access token.

Tokens are verified here as well as at the API gateway, so the service stays protected when
its port is reached directly.
"""

from dataclasses import dataclass
from typing import Awaitable, Callable, Optional
from urllib.parse import quote

import httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import settings

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Caller:
    user_id: str
    role: str
    token: str

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def caller_from_token(token: str) -> Caller:
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
    return caller_from_token(credentials.credentials)


def require_admin(caller: Caller = Depends(require_caller)) -> Caller:
    if not caller.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return caller


def ensure_self_or_admin(user_id: Optional[str], caller: Caller) -> None:
    """Users may only act for themselves; admins may act for anyone."""
    if not caller.is_admin and user_id != caller.user_id:
        raise HTTPException(status_code=403, detail="Not allowed for another user")


async def booking_visible_to(booking_id: str, caller: Caller) -> bool:
    """Whether booking_service shows this booking to the caller (its customer, provider, shop or an admin).

    booking_service applies its own access rules to the caller's token, so a 404 means the caller
    is not a party to the booking (or it does not exist).
    """
    async with httpx.AsyncClient(base_url=settings.BOOKING_SERVICE_URL, timeout=5.0) as client:
        try:
            # Quoted so an id like "../bookings" cannot point the check at another endpoint.
            resp = await client.get(
                f"/api/v1/bookings/{quote(booking_id, safe='')}", headers={"Authorization": f"Bearer {caller.token}"}
            )
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=503, detail="Booking service unavailable") from exc
    if resp.status_code == 200:
        return True
    if resp.status_code in (403, 404):
        return False
    raise HTTPException(status_code=503, detail="Booking service unavailable")


BookingCheck = Callable[[str, Caller], Awaitable[bool]]


def get_booking_check() -> BookingCheck:
    return booking_visible_to
