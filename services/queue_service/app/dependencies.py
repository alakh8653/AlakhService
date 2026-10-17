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


async def _get_json(base_url: str, path: str) -> Optional[dict]:
    async with httpx.AsyncClient(base_url=base_url, timeout=5.0) as client:
        try:
            resp = await client.get(path)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=503, detail="Upstream service unavailable") from exc
    if resp.status_code == 404:
        return None
    if resp.status_code != 200:
        raise HTTPException(status_code=503, detail="Upstream service unavailable")
    return resp.json()


async def fetch_service_owner(service_id: str) -> Optional[str]:
    """Owner of the shop that offers a catalogue service, or None if either does not exist."""
    # Ids are quoted so one like "../x" names a (missing) service instead of another endpoint.
    listing = await _get_json(settings.SERVICE_CATALOG_URL, f"/api/v1/services/{quote(service_id, safe='')}")
    if not listing:
        return None
    shop = await _get_json(settings.SHOP_SERVICE_URL, f"/api/v1/shops/{quote(str(listing['shop_id']), safe='')}")
    return shop.get("owner_id") if shop else None


OwnerLookup = Callable[[str], Awaitable[Optional[str]]]


def get_service_owner_lookup() -> OwnerLookup:
    return fetch_service_owner
