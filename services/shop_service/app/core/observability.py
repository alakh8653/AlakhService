"""Request ids in every log line, JSON logs in production, and a readiness check of real dependencies.

The gateway gives each request an X-Request-ID; binding it to the log context here means one id
finds a request in the gateway's log and in every service log it touched.
"""

import asyncio
import re
import uuid

import structlog
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings
from app.database import engine

_REQUEST_ID = re.compile(r"^[\w-]{1,128}$")
_CHECK_TIMEOUT_SECONDS = 2.0


def configure_logging() -> None:
    renderer = (
        structlog.processors.JSONRenderer() if settings.ENVIRONMENT == "production" else structlog.dev.ConsoleRenderer()
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.format_exc_info,
            renderer,
        ]
    )


class RequestIdMiddleware:
    """Takes the gateway's X-Request-ID (or makes one), logs with it, and returns it."""

    def __init__(self, app, service: str):
        self.app = app
        self.service = service

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)
        incoming = dict(scope.get("headers") or []).get(b"x-request-id", b"").decode("latin-1")
        request_id = incoming if _REQUEST_ID.match(incoming) else uuid.uuid4().hex
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id, service=self.service)

        async def send_with_id(message):
            if message["type"] == "http.response.start":
                message["headers"] = [*message.get("headers", []), (b"x-request-id", request_id.encode())]
            await send(message)

        await self.app(scope, receive, send_with_id)


async def _database() -> None:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


async def _redis() -> None:
    import redis.asyncio as aioredis

    client = aioredis.from_url(settings.REDIS_URL)
    try:
        await client.ping()
    finally:
        await client.aclose()


async def _check(probe) -> str:
    try:
        await asyncio.wait_for(probe(), _CHECK_TIMEOUT_SECONDS)
        return "ok"
    except Exception as e:  # noqa: BLE001 - any failure means not ready
        return f"failing: {type(e).__name__}"


def install_observability(app: FastAPI, service: str, check_redis: bool = False) -> None:
    configure_logging()
    app.add_middleware(RequestIdMiddleware, service=service)

    @app.get("/ready", include_in_schema=False)
    async def ready():
        """Ready to serve: the database answers (and Redis, where this service needs it).

        /health only says the process is up; orchestrators should route traffic on this.
        """
        checks = {"database": await _check(_database)}
        if check_redis:
            checks["redis"] = await _check(_redis)
        ok = all(result == "ok" for result in checks.values())
        return JSONResponse(
            {"status": "ready" if ok else "not_ready", "service": service, "checks": checks},
            status_code=200 if ok else 503,
        )
