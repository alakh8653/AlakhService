from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    APP_NAME: str = "Auth Service"
    SECRET_KEY: str = "change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    DATABASE_URL: str = "postgresql+asyncpg://alakh:alakh_secret@postgres:5432/auth_db"
    REDIS_URL: str = "redis://redis:6379/0"
    CORS_ORIGINS: List[str] = ["*"]
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_DURATION_SECONDS: int = 300
    OTP_EXPIRE_SECONDS: int = 300
    
    class Config:
        env_file = ".env"

settings = Settings()
