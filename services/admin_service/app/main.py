from contextlib import asynccontextmanager

import structlog
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.dependencies import require_admin
from app.routers.access import router as access_router
from app.routers.admin import router as admin_router

logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("service_starting", service=settings.APP_NAME)
    yield
    logger.info("service_stopping", service=settings.APP_NAME)

app = FastAPI(title=settings.APP_NAME, version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
# Everything here is for platform admins (the gateway enforces the same).
app.include_router(admin_router, prefix="/api/v1", tags=["admin"], dependencies=[Depends(require_admin)])
app.include_router(access_router, prefix="/api/v1", tags=["access"], dependencies=[Depends(require_admin)])

@app.get("/health")
async def health():
    return {"status": "healthy", "service": settings.APP_NAME}
