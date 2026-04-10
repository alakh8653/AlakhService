from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    APP_NAME: str = "Catalog Service"
    DATABASE_URL: str = "postgresql+asyncpg://alakh:alakh_secret@postgres:5432/catalog_db"
    REDIS_URL: str = "redis://redis:6379/5"
    CORS_ORIGINS: List[str] = ["*"]
    CACHE_TTL_SECONDS: int = 300

    class Config:
        env_file = ".env"

settings = Settings()
