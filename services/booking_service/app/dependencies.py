from typing import Awaitable, Callable, Optional
from urllib.parse import quote

import httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import settings

security = HTTPBearer()


def path_segment(value: str) -> str:
    """A client-supplied id as exactly one URL path segment of an internal call.

    quote() leaves "." alone and httpx resolves "..", so dots are escaped too.
    """
    return quote(value, safe="").replace(".", "%2E")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    return verify_access_token(credentials.credentials)


def verify_access_token(token: str) -> dict:
    """The claims of a valid access token; 401 for anything else."""
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
            resp = await client.get(f"/api/v1/shops/{path_segment(shop_id)}")
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
            resp = await client.get(f"/api/v1/services/{path_segment(service_id)}")
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


class CouponRejected(Exception):
    """The coupon can't be used for this booking; the message says why."""


async def price_with_coupon(token: str, customer_id: str, service_id: str, list_price: int, code: str) -> int:
    """The price after [code]'s discount, with the coupon used up for this customer (pricing_engine).

    Runs as the customer (their token), so the coupon's once-per-customer rule applies to them.
    """
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(base_url=settings.PRICING_ENGINE_URL, timeout=5.0, headers=headers) as client:
        try:
            check = await client.get(f"/api/v1/coupons/{path_segment(code)}/validate")
            if check.status_code == 404:
                raise CouponRejected("Coupon not found")
            check.raise_for_status()
            if not check.json().get("is_valid"):
                raise CouponRejected(check.json().get("message") or "Coupon is not valid")
            priced = await client.post(
                "/api/v1/pricing/calculate",
                json={
                    "service_id": service_id,
                    "customer_id": customer_id,
                    "base_price_cents": list_price,
                    "coupon_code": code,
                },
            )
            priced.raise_for_status()
            # Only services may redeem, so a coupon is used up only by a booking made here.
            redeemed = await client.post(
                f"/internal/pricing/{path_segment(str(priced.json()['id']))}/redeem",
                headers={"X-Internal-Key": settings.INTERNAL_API_KEY},
            )
            if redeemed.status_code == 409:
                raise CouponRejected(redeemed.json().get("detail") or "Coupon already used")
            redeemed.raise_for_status()
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=503, detail="Pricing service unavailable") from exc
    return int(redeemed.json()["final_price_cents"])


CouponPricer = Callable[[str, str, str, int, str], Awaitable[int]]


def get_coupon_pricer() -> CouponPricer:
    return price_with_coupon
