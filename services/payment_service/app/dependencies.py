from typing import Awaitable, Callable, Optional

import httpx
import redis.asyncio as aioredis
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import settings

security = HTTPBearer()


async def get_redis():
    client = aioredis.from_url(settings.REDIS_URL)
    try:
        yield client
    finally:
        await client.close()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from None
    # Refresh and single-purpose (e.g. password reset) tokens share the signing key; reject them.
    if not payload.get("sub") or payload.get("type") != "access" or "purpose" in payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload


async def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


async def _get_json(base_url: str, path: str, token: Optional[str] = None) -> Optional[dict]:
    headers = {"Authorization": f"Bearer {token}"} if token else None
    async with httpx.AsyncClient(base_url=base_url, timeout=5.0) as client:
        try:
            resp = await client.get(path, headers=headers)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=503, detail="Upstream service unavailable") from exc
    if resp.status_code in (403, 404):
        return None
    if resp.status_code != 200:
        raise HTTPException(status_code=503, detail="Upstream service unavailable")
    return resp.json()


async def fetch_booking(booking_id: str, token: str) -> Optional[dict]:
    """The booking as booking_service shows it to the caller (None if they may not see it)."""
    return await _get_json(settings.BOOKING_SERVICE_URL, f"/api/v1/bookings/{booking_id}", token)


async def fetch_shop_owner(shop_id: str) -> Optional[str]:
    shop = await _get_json(settings.SHOP_SERVICE_URL, f"/api/v1/shops/{shop_id}")
    return shop.get("owner_id") if shop else None


BookingLookup = Callable[[str, str], Awaitable[Optional[dict]]]
OwnerLookup = Callable[[str], Awaitable[Optional[str]]]


def get_booking_lookup() -> BookingLookup:
    return fetch_booking


def get_shop_owner_lookup() -> OwnerLookup:
    return fetch_shop_owner
