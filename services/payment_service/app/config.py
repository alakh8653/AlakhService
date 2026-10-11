from typing import List, Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Payment Service"
    SECRET_KEY: str = "change-in-production"
    ALGORITHM: str = "HS256"
    DATABASE_URL: str = "postgresql+asyncpg://alakh:alakh_secret@postgres:5432/payment_db"
    REDIS_URL: str = "redis://redis:6379/3"
    CORS_ORIGINS: List[str] = ["*"]
    RAZORPAY_KEY_ID: Optional[str] = None
    RAZORPAY_KEY_SECRET: Optional[str] = None
    # Set in the Razorpay dashboard when adding the webhook; without it webhooks are refused.
    RAZORPAY_WEBHOOK_SECRET: Optional[str] = None
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    PLATFORM_ACCOUNT_ID: str = "platform_account"
    BOOKING_SERVICE_URL: str = "http://booking_service:8000"
    SHOP_SERVICE_URL: str = "http://shop_service:8000"

    class Config:
        env_file = ".env"


settings = Settings()
