from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog
from app.config import settings
from app.routers.payments import router as payments_router

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("payment_service_starting", service="payment_service")
    yield
    logger.info("payment_service_stopping", service="payment_service")


app = FastAPI(
    title="Payment Service",
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

app.include_router(payments_router, prefix="/api/v1", tags=["payments"])


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "payment_service"}


@app.get("/ready")
async def ready():
    return {"status": "ready"}
