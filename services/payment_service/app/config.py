from pydantic_settings import BaseSettings
from typing import List, Optional


class Settings(BaseSettings):
    APP_NAME: str = "Payment Service"
    SECRET_KEY: str = "change-in-production"
    ALGORITHM: str = "HS256"
    DATABASE_URL: str = "postgresql+asyncpg://alakh:alakh_secret@postgres:5432/payment_db"
    REDIS_URL: str = "redis://redis:6379/3"
    CORS_ORIGINS: List[str] = ["*"]
    RAZORPAY_KEY_ID: Optional[str] = None
    RAZORPAY_KEY_SECRET: Optional[str] = None
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    PLATFORM_ACCOUNT_ID: str = "platform_account"

    class Config:
        env_file = ".env"


settings = Settings()
