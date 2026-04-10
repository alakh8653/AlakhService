from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog
from app.config import settings
from app.routers.notifications import router as notif_router
from app.core.exceptions import NotificationServiceError, NotificationNotFoundError, TemplateNotFoundError

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("notification_service_starting", service="notification_service")
    yield
    logger.info("notification_service_stopping", service="notification_service")


app = FastAPI(
    title="Notification Service",
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


@app.exception_handler(TemplateNotFoundError)
async def template_not_found_handler(request: Request, exc: TemplateNotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(NotificationNotFoundError)
async def notification_not_found_handler(request: Request, exc: NotificationNotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(NotificationServiceError)
async def notification_error_handler(request: Request, exc: NotificationServiceError):
    return JSONResponse(status_code=500, content={"detail": str(exc)})


app.include_router(notif_router, prefix="/api/v1", tags=["notifications"])


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "notification_service"}


@app.get("/ready")
async def ready():
    return {"status": "ready"}
