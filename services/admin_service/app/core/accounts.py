"""Switches accounts on and off in auth_service, which is what makes a ban stop someone signing in."""

from typing import Awaitable, Callable
from urllib.parse import quote

import httpx
from fastapi import HTTPException

from app.config import settings

AccountSwitch = Callable[[str, bool], Awaitable[None]]


async def set_account_active(user_id: str, active: bool) -> None:
    if not settings.INTERNAL_API_KEY:
        raise HTTPException(status_code=503, detail="Bans cannot be enforced: INTERNAL_API_KEY is not configured")
    try:
        async with httpx.AsyncClient(base_url=settings.AUTH_SERVICE_URL, timeout=5.0) as client:
            # Quoted so a user id like "../x" cannot aim the internal key at another endpoint.
            resp = await client.post(
                f"/internal/users/{quote(user_id, safe='')}/status",
                json={"is_active": active},
                headers={"X-Internal-Key": settings.INTERNAL_API_KEY},
            )
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail="Auth service unavailable") from e
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="User not found")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Auth service refused the change")


def get_account_switch() -> AccountSwitch:
    return set_account_active
