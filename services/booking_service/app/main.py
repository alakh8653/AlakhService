import asyncio
from contextlib import asynccontextmanager, suppress

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.observability import install_observability
from app.routers.availability import router as availability_router
from app.routers.bookings import router as bookings_router
from app.routers.chat import router as chat_router
from app.routers.internal import router as internal_router

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("booking_service_starting", service="booking_service")
    worker = None
    if settings.REMINDERS_ENABLED:
        from app.core.notifier import get_notifier
        from app.core.payments import get_payment_client, get_session_factory
        from app.core.worker import run_forever
        from app.dependencies import fetch_shop_owner

        worker = asyncio.create_task(
            run_forever(get_session_factory(), get_notifier(), fetch_shop_owner, get_payment_client())
        )
    yield
    if worker is not None:
        worker.cancel()
        with suppress(asyncio.CancelledError):
            await worker
    logger.info("booking_service_stopping", service="booking_service")


app = FastAPI(
    title="Booking Service",
    version="1.0.0",
    lifespan=lifespan,
)
install_observability(app, service="booking_service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(bookings_router, prefix="/api/v1", tags=["bookings"])
app.include_router(availability_router, prefix="/api/v1", tags=["availability"])
app.include_router(chat_router, prefix="/api/v1", tags=["chat"])
app.include_router(internal_router, tags=["internal"])


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "booking_service"}
