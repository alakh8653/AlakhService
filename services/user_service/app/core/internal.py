"""Calls from other platform services, authenticated with the shared INTERNAL_API_KEY.

These routes live outside /api/v1, which is all the gateway forwards, so only services on the
internal network reach them; the key keeps out anything else that can reach the port.
"""

import hmac
from typing import Optional

from fastapi import Header, HTTPException

from app.config import settings


def is_internal(x_internal_key: Optional[str]) -> bool:
    return bool(
        settings.INTERNAL_API_KEY and x_internal_key and hmac.compare_digest(x_internal_key, settings.INTERNAL_API_KEY)
    )


def require_internal(x_internal_key: Optional[str] = Header(None)) -> None:
    if not settings.INTERNAL_API_KEY:
        raise HTTPException(status_code=503, detail="Internal API is not configured")
    if not is_internal(x_internal_key):
        raise HTTPException(status_code=401, detail="Invalid internal key")
