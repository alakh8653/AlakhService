from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog
from app.config import settings
from app.routers.catalog import router as catalog_router

logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("service_starting", service=settings.APP_NAME)
    yield
    logger.info("service_stopping", service=settings.APP_NAME)

app = FastAPI(title=settings.APP_NAME, version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(catalog_router, prefix="/api/v1", tags=["catalog"])

@app.get("/health")
async def health():
    return {"status": "healthy", "service": settings.APP_NAME}
