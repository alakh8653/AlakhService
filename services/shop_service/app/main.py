from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.observability import install_observability
from app.routers.reviews import router as reviews_router
from app.routers.shop import router as shop_router
from app.routers.staff import router as staff_router

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("service_starting", service=settings.APP_NAME)
    yield
    logger.info("service_stopping", service=settings.APP_NAME)


app = FastAPI(title=settings.APP_NAME, version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
install_observability(app, service="shop_service")
# Before the shop routes, whose /shops/{shop_id} would otherwise take /shops/ratings.
app.include_router(reviews_router, prefix="/api/v1", tags=["reviews"])
app.include_router(shop_router, prefix="/api/v1", tags=["shops"])
app.include_router(staff_router, prefix="/api/v1", tags=["staff"])


@app.get("/health")
async def health():
    return {"status": "healthy", "service": settings.APP_NAME}
