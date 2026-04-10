from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    APP_NAME: str = "Booking Service"
    SECRET_KEY: str = "change-in-production"
    ALGORITHM: str = "HS256"
    DATABASE_URL: str = "postgresql+asyncpg://alakh:alakh_secret@postgres:5432/booking_db"
    REDIS_URL: str = "redis://redis:6379/2"
    CORS_ORIGINS: List[str] = ["*"]

    class Config:
        env_file = ".env"


settings = Settings()
