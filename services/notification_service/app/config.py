from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Notification Service"
    DATABASE_URL: str = "postgresql+asyncpg://alakh:alakh_secret@postgres:5432/notification_db"
    REDIS_URL: str = "redis://redis:6379/4"
    CORS_ORIGINS: List[str] = ["*"]
    SECRET_KEY: str = "change-in-production"
    ALGORITHM: str = "HS256"

    # Firebase service account for push (FCM HTTP v1): the JSON itself, or a path to the file.
    FCM_SERVICE_ACCOUNT_JSON: str = ""
    FCM_SERVICE_ACCOUNT_FILE: str = ""

    # Shared secret other platform services present on /internal routes.
    INTERNAL_API_KEY: str = ""

    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = ""

    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "noreply@alakh.com"
    SMTP_FROM_NAME: str = "Alakh"

    MAX_RETRY_ATTEMPTS: int = 3
    RETRY_BASE_DELAY: float = 1.0

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
