from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.exceptions import (
    AccountLockedError,
    AuthServiceError,
    OTPRateLimitedError,
    OTPTooManyAttemptsError,
    UserAlreadyExistsError,
)
from app.core.observability import install_observability
from app.routers.auth import router as auth_router
from app.routers.users import internal_router
from app.routers.users import router as users_router

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("auth_service_starting", service="auth_service")
    yield
    logger.info("auth_service_stopping", service="auth_service")


app = FastAPI(
    title="Auth Service",
    version="1.0.0",
    lifespan=lifespan,
)
install_observability(app, service="auth_service", check_redis=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AuthServiceError)
async def auth_error_handler(request: Request, exc: AuthServiceError):
    if isinstance(exc, AccountLockedError):
        return JSONResponse(
            status_code=429,
            content={"detail": str(exc), "lockout_seconds": exc.lockout_seconds},
        )
    if isinstance(exc, (OTPRateLimitedError, OTPTooManyAttemptsError)):
        return JSONResponse(status_code=429, content={"detail": str(exc)})
    if isinstance(exc, UserAlreadyExistsError):
        return JSONResponse(status_code=409, content={"detail": str(exc)})
    return JSONResponse(status_code=401, content={"detail": str(exc)})


app.include_router(auth_router, prefix="/api/v1", tags=["auth"])
app.include_router(users_router, prefix="/api/v1", tags=["users"])
# Service-to-service only: outside /api/v1, so the gateway never forwards it.
app.include_router(internal_router, tags=["internal"])


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "auth_service"}
