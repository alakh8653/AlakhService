"""What a shop is shown of its customers: a display name ("Ravi S."), never their contact details.

The same as booking_service's app/core/names.py (services share no code).

auth_service holds the names and turns them into display names; it is asked for a page of customers at
once, and the answers are kept for a short while. When it cannot be reached every customer reads
"Customer": a booking list is never refused for want of a name.
"""

import time
from typing import Awaitable, Callable, Dict, Iterable, Optional, Tuple

import httpx
import structlog

from app.config import settings

log = structlog.get_logger()

FALLBACK = "Customer"
CACHE_SECONDS = 120.0
_CACHE_MAX = 5000
_cache: Dict[str, Tuple[float, str]] = {}

NameLookup = Callable[[Iterable[str]], Awaitable[Dict[str, str]]]


async def fetch_display_names(
    user_ids: Iterable[str], transport: Optional[httpx.AsyncBaseTransport] = None
) -> Dict[str, str]:
    """A display name for every id (FALLBACK for those auth_service does not answer for)."""
    ids = list(dict.fromkeys(i for i in user_ids if i))
    now = time.monotonic()
    names = {}
    missing = []
    for uid in ids:
        cached = _cache.get(uid)
        if cached and cached[0] > now:
            names[uid] = cached[1]
        else:
            missing.append(uid)
    if missing and settings.INTERNAL_API_KEY:
        try:
            async with httpx.AsyncClient(
                base_url=settings.AUTH_SERVICE_URL, timeout=httpx.Timeout(3.0, connect=1.0), transport=transport
            ) as client:
                for start in range(0, len(missing), 200):
                    resp = await client.post(
                        "/internal/users/display-names",
                        json={"user_ids": missing[start : start + 200]},
                        headers={"X-Internal-Key": settings.INTERNAL_API_KEY},
                    )
                    resp.raise_for_status()
                    found = resp.json().get("names") or {}
                    if len(_cache) >= _CACHE_MAX:
                        _cache.clear()
                    for uid, name in found.items():
                        if isinstance(name, str) and name:
                            names[uid] = name
                            _cache[uid] = (now + CACHE_SECONDS, name)
        except (httpx.HTTPError, ValueError) as e:
            # Not cached, so names come back as soon as auth_service does.
            log.warning("display_names_unavailable", error=str(e))
    return {uid: names.get(uid, FALLBACK) for uid in ids}


def get_name_lookup() -> NameLookup:
    return fetch_display_names
