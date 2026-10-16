from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Dispute Service"
    DATABASE_URL: str = "postgresql+asyncpg://alakh:alakh_secret@postgres:5432/dispute_db"
    REDIS_URL: str = "redis://redis:6379/0"
    CORS_ORIGINS: List[str] = ["*"]
    SECRET_KEY: str = "change-in-production"
    ALGORITHM: str = "HS256"
    BOOKING_SERVICE_URL: str = "http://booking_service:8000"

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
