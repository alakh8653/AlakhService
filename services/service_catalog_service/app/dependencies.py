"""Caller identity from the bearer access token, and shop ownership checks.

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

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def require_caller(credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer)) -> Caller:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from None
    # Refresh and single-purpose (e.g. password reset) tokens share the signing key; reject them.
    if not payload.get("sub") or payload.get("type") != "access" or "purpose" in payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return Caller(payload["sub"], payload.get("role") or "user")


def require_admin(caller: Caller = Depends(require_caller)) -> Caller:
    if not caller.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return caller


async def fetch_shop_owner(shop_id: str) -> Optional[str]:
    """Owner user id of a shop according to shop_service, or None if the shop does not exist."""
    async with httpx.AsyncClient(base_url=settings.SHOP_SERVICE_URL, timeout=5.0) as client:
        try:
            resp = await client.get(f"/api/v1/shops/{shop_id}")
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=503, detail="Shop service unavailable") from exc
    if resp.status_code == 404:
        return None
    if resp.status_code != 200:
        raise HTTPException(status_code=503, detail="Shop service unavailable")
    return resp.json().get("owner_id")


OwnerLookup = Callable[[str], Awaitable[Optional[str]]]


def get_shop_owner_lookup() -> OwnerLookup:
    return fetch_shop_owner


async def ensure_shop_owner(shop_id: str, caller: Caller, lookup_owner: OwnerLookup) -> None:
    """Only the shop's owner (or an admin) may manage its listings."""
    if caller.is_admin:
        return
    owner = await lookup_owner(shop_id)
    if owner is None:
        raise HTTPException(status_code=404, detail="Shop not found")
    if owner != caller.user_id:
        raise HTTPException(status_code=403, detail="Not your shop")
