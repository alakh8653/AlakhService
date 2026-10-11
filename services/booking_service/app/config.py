from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Booking Service"
    SECRET_KEY: str = "change-in-production"
    ALGORITHM: str = "HS256"
    DATABASE_URL: str = "postgresql+asyncpg://alakh:alakh_secret@postgres:5432/booking_db"
    REDIS_URL: str = "redis://redis:6379/2"
    SHOP_SERVICE_URL: str = "http://shop_service:8000"
    SERVICE_CATALOG_URL: str = "http://service_catalog_service:8000"
    NOTIFICATION_SERVICE_URL: str = "http://notification_service:8000"
    # Shared with notification_service; without it no notifications are sent.
    INTERNAL_API_KEY: str = ""
    # Times in notifications are shown in this zone.
    DISPLAY_TIMEZONE: str = "Asia/Kolkata"
    CORS_ORIGINS: List[str] = ["*"]

    class Config:
        env_file = ".env"


settings = Settings()
