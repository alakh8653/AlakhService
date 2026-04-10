from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog
from app.config import settings
from app.routers.catalog import router as catalog_router
from app.core.exceptions import CatalogServiceError, CategoryNotFoundError, ServiceNotFoundError, SlugConflictError

logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("catalog_service_starting", service="catalog_service")
    yield
    logger.info("catalog_service_stopping", service="catalog_service")

app = FastAPI(title="Catalog Service", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.exception_handler(CategoryNotFoundError)
async def category_not_found(request: Request, exc: CategoryNotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})

@app.exception_handler(ServiceNotFoundError)
async def service_not_found(request: Request, exc: ServiceNotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})

@app.exception_handler(SlugConflictError)
async def slug_conflict(request: Request, exc: SlugConflictError):
    return JSONResponse(status_code=409, content={"detail": str(exc)})

@app.exception_handler(CatalogServiceError)
async def catalog_error(request: Request, exc: CatalogServiceError):
    return JSONResponse(status_code=500, content={"detail": str(exc)})

app.include_router(catalog_router, prefix="/api/v1", tags=["catalog"])

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "catalog_service"}

@app.get("/ready")
async def ready():
    return {"status": "ready"}
