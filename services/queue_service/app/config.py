from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Queue Service"
    DATABASE_URL: str = "postgresql+asyncpg://alakh:alakh_secret@postgres:5432/queue_db"
    REDIS_URL: str = "redis://redis:6379/0"
    CORS_ORIGINS: List[str] = ["*"]
    SECRET_KEY: str = "change-in-production"
    ALGORITHM: str = "HS256"
    SERVICE_CATALOG_URL: str = "http://service_catalog_service:8000"
    SHOP_SERVICE_URL: str = "http://shop_service:8000"

    class Config:
        env_file = ".env"

settings = Settings()
