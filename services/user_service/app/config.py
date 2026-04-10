from pydantic_settings import BaseSettings
from typing import List, Optional


class Settings(BaseSettings):
    APP_NAME: str = "User Service"
    SECRET_KEY: str = "change-in-production"
    ALGORITHM: str = "HS256"
    DATABASE_URL: str = "postgresql+asyncpg://alakh:alakh_secret@postgres:5432/user_db"
    REDIS_URL: str = "redis://redis:6379/1"
    CORS_ORIGINS: List[str] = ["*"]
    S3_BUCKET: Optional[str] = None
    S3_REGION: Optional[str] = "us-east-1"
    S3_ACCESS_KEY: Optional[str] = None
    S3_SECRET_KEY: Optional[str] = None
    MAX_AVATAR_SIZE_MB: int = 5

    class Config:
        env_file = ".env"


settings = Settings()
