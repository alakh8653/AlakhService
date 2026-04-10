from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog
from app.config import settings
from app.routers.users import router as users_router

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("user_service_starting", service="user_service")
    yield
    logger.info("user_service_stopping", service="user_service")


app = FastAPI(
    title="User Service",
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

app.include_router(users_router, prefix="/api/v1", tags=["users"])


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "user_service"}


@app.get("/ready")
async def ready():
    return {"status": "ready"}
