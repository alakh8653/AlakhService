from typing import Awaitable, Callable, Optional

import httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import settings

security = HTTPBearer()


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


def get_shop_owner_lookup() -> Callable[[str], Awaitable[Optional[str]]]:
    return fetch_shop_owner


async def require_shop_access(
    shop_id: str,
    current_user: dict = Depends(get_current_user),
    lookup_owner: Callable[[str], Awaitable[Optional[str]]] = Depends(get_shop_owner_lookup),
) -> str:
    """Only the shop's owner (or an admin) may see its bookings."""
    if current_user.get("role") == "admin":
        return shop_id
    owner = await lookup_owner(shop_id)
    if owner is None:
        raise HTTPException(status_code=404, detail="Shop not found")
    if owner != current_user.get("sub"):
        raise HTTPException(status_code=403, detail="Not your shop")
    return shop_id


async def fetch_service_listing(service_id: str) -> Optional[dict]:
    """The service catalogue's listing (price_cents, duration_minutes, shop_id, is_active), or None."""
    async with httpx.AsyncClient(base_url=settings.SERVICE_CATALOG_URL, timeout=5.0) as client:
        try:
            resp = await client.get(f"/api/v1/services/{service_id}")
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=503, detail="Service catalogue unavailable") from exc
    if resp.status_code == 404:
        return None
    if resp.status_code != 200:
        raise HTTPException(status_code=503, detail="Service catalogue unavailable")
    return resp.json()


def get_service_lookup() -> Callable[[str], Awaitable[Optional[dict]]]:
    return fetch_service_listing


async def fetch_shop_provider_ids(shop_id: str, token: str) -> set:
    """User ids of the shop's active staff, as shop_service shows them to the caller (the owner)."""
    async with httpx.AsyncClient(base_url=settings.SHOP_SERVICE_URL, timeout=5.0) as client:
        try:
            resp = await client.get(
                "/api/v1/staff", params={"shop_id": shop_id}, headers={"Authorization": f"Bearer {token}"}
            )
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=503, detail="Shop service unavailable") from exc
    if resp.status_code != 200:
        raise HTTPException(status_code=503, detail="Shop service unavailable")
    return {m["user_id"] for m in resp.json() if m.get("user_id") and m.get("is_active")}


def get_staff_lookup() -> Callable[[str, str], Awaitable[set]]:
    return fetch_shop_provider_ids
