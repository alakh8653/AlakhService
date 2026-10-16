from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Admin Service"
    DATABASE_URL: str = "postgresql+asyncpg://alakh:alakh_secret@postgres:5432/admin_db"
    REDIS_URL: str = "redis://redis:6379/0"
    CORS_ORIGINS: List[str] = ["*"]
    SECRET_KEY: str = "change-in-production"
    ALGORITHM: str = "HS256"
    AUTH_SERVICE_URL: str = "http://auth_service:8000"
    # Shared with auth_service; bans are enforced there by deactivating the account.
    INTERNAL_API_KEY: str = ""

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
