from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog
from app.config import settings
from app.routers.bookings import router as bookings_router

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("booking_service_starting", service="booking_service")
    yield
    logger.info("booking_service_stopping", service="booking_service")


app = FastAPI(
    title="Booking Service",
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

app.include_router(bookings_router, prefix="/api/v1", tags=["bookings"])


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "booking_service"}


@app.get("/ready")
async def ready():
    return {"status": "ready"}
