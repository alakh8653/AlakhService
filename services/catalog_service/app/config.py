from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Catalog Service"
    DATABASE_URL: str = "postgresql+asyncpg://alakh:alakh_secret@postgres:5432/catalog_db"
    REDIS_URL: str = "redis://redis:6379/5"
    CORS_ORIGINS: List[str] = ["*"]
    SECRET_KEY: str = "change-in-production"
    ALGORITHM: str = "HS256"
    CACHE_TTL_SECONDS: int = 300

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
