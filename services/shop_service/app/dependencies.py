"""Caller identity from the bearer access token.

Tokens are verified here rather than trusting gateway-set headers, because the service port can
be reached without going through the gateway.
"""

from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

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


def ensure_owner(owner_id: str, caller: Caller) -> None:
    if not caller.is_admin and caller.user_id != owner_id:
        raise HTTPException(status_code=403, detail="Not your shop")


async def fetch_booking(booking_id: str, caller: Caller) -> Optional[dict]:
    """The booking as booking_service shows it to the caller, or None if they may not see it."""
    async with httpx.AsyncClient(base_url=settings.BOOKING_SERVICE_URL, timeout=5.0) as client:
        try:
            resp = await client.get(
                f"/api/v1/bookings/{booking_id}", headers={"Authorization": f"Bearer {caller.token}"}
            )
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=503, detail="Booking service unavailable") from exc
    if resp.status_code in (403, 404):
        return None
    if resp.status_code != 200:
        raise HTTPException(status_code=503, detail="Booking service unavailable")
    return resp.json()


BookingLookup = Callable[[str, Caller], Awaitable[Optional[dict]]]


def get_booking_lookup() -> BookingLookup:
    return fetch_booking
