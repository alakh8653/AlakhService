from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog
from app.config import settings
from app.routers.auth import router as auth_router
from app.core.exceptions import AuthServiceError, AccountLockedError

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
    return JSONResponse(status_code=401, content={"detail": str(exc)})


app.include_router(auth_router, prefix="/api/v1", tags=["auth"])


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "auth_service"}


@app.get("/ready")
async def ready():
    return {"status": "ready"}
