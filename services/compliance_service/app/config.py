from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    APP_NAME: str = "Compliance Service"
    DATABASE_URL: str = "postgresql+asyncpg://alakh:alakh_secret@postgres:5432/compliance_db"
    REDIS_URL: str = "redis://redis:6379/0"
    CORS_ORIGINS: List[str] = ["*"]

    class Config:
        env_file = ".env"

settings = Settings()
