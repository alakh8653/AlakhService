"""Ends access tokens before they expire, through markers the API gateway checks on every request.

Access tokens are self-contained and last ACCESS_TOKEN_EXPIRE_MINUTES. Signing out (or a ban, a
password reset, a deleted account) also has to stop the access tokens already handed out:

  auth:revoked_before:{user id} = time: every token the user was issued before it is refused
  auth:revoked_sid:{session id} = 1: every token of one signed-in device is refused

Markers only need to outlive the tokens they stop. Writing them is best effort: the refresh tokens
are already revoked in the database, so a Redis outage only means old access tokens run their course.
"""

import time

import redis.asyncio as aioredis
import structlog

from app.config import settings

log = structlog.get_logger()

# A little longer than an access token lives, so no token outlives its marker.
_TTL_SECONDS = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60 + 300


async def revoke_user_tokens(redis: aioredis.Redis, user_id: str) -> None:
    """Every access token issued to the user so far stops working."""
    try:
        await redis.set(f"auth:revoked_before:{user_id}", str(time.time()), ex=_TTL_SECONDS)
    except Exception as e:  # noqa: BLE001 - Redis down must not fail the sign-out itself
        log.warning("revocation_not_recorded", user_id=user_id, error=str(e))


async def revoke_session(redis: aioredis.Redis, session_id: str) -> None:
    """Access tokens of one signed-in device stop working."""
    try:
        await redis.set(f"auth:revoked_sid:{session_id}", "1", ex=_TTL_SECONDS)
    except Exception as e:  # noqa: BLE001
        log.warning("revocation_not_recorded", session_id=session_id, error=str(e))
