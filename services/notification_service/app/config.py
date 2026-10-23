from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Notification Service"
    DATABASE_URL: str = "postgresql+asyncpg://alakh:alakh_secret@postgres:5432/notification_db"
    REDIS_URL: str = "redis://redis:6379/4"
    # Browsers talk to the gateway, never to a service directly, so no cross-origin access by default.
    CORS_ORIGINS: List[str] = []
    # "production" turns on the checks at the bottom of this file.
    ENVIRONMENT: str = "development"
    SECRET_KEY: str = "change-in-production"
    ALGORITHM: str = "HS256"

    # Firebase service account for push (FCM HTTP v1): the JSON itself, or a path to the file.
    FCM_SERVICE_ACCOUNT_JSON: str = ""
    FCM_SERVICE_ACCOUNT_FILE: str = ""

    # Shared secret other platform services present on /internal routes.
    INTERNAL_API_KEY: str = ""

    # Where a person's own phone/email is looked up for SMS and email fallbacks (needs INTERNAL_API_KEY).
    AUTH_SERVICE_URL: str = "http://auth_service:8000"
    # Linked from the email a shop owner gets for a new booking (e.g. https://shop.<DOMAIN>); optional.
    SHOP_DASHBOARD_URL: str = ""

    # Who sends SMS: twilio, msg91 (Indian DLT-registered sender) or none.
    SMS_PROVIDER: str = "twilio"
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = ""
    # MSG91: auth key, the DLT sender id (header), and one DLT template id per event texted. The
    # registered templates must match app/core/events.py SMS_TEXTS word for word. An event without a
    # template id is not texted (it falls back to email).
    MSG91_AUTH_KEY: str = ""
    MSG91_SENDER_ID: str = ""
    MSG91_API_URL: str = "https://api.msg91.com/api/v2/sendsms"
    MSG91_TEMPLATE_BOOKING_CONFIRMED: str = ""
    MSG91_TEMPLATE_BOOKING_CANCELLED: str = ""
    MSG91_TEMPLATE_BOOKING_REMINDER: str = ""
    MSG91_TEMPLATE_BOOKING_REFUNDED: str = ""
    MSG91_TEMPLATE_BOOKING_EXPIRED: str = ""

    # Without SMTP_HOST no email is sent.
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True
    SMTP_FROM_EMAIL: str = "noreply@alakhservice.com"
    SMTP_FROM_NAME: str = "AlakhService"

    MAX_RETRY_ATTEMPTS: int = 3
    RETRY_BASE_DELAY: float = 1.0

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()


# Values that are only safe on a developer's machine: a production deployment refuses to start with
# them rather than run with a key anyone can look up (a known SECRET_KEY lets anyone sign admin tokens).
_PLACEHOLDER_SECRETS = {
    "change-in-production",
    "changeme",
    "change-me",
    "secret",
    "dev-secret",
    "your-secret-key",
    "your-super-secret-jwt-key-change-in-production",
}


def production_problems(s: Settings) -> List[str]:
    problems = []
    if s.SECRET_KEY in _PLACEHOLDER_SECRETS or len(s.SECRET_KEY) < 32:
        problems.append("SECRET_KEY is a placeholder or shorter than 32 characters")
    if "*" in s.CORS_ORIGINS:
        problems.append("CORS_ORIGINS must not be *")
    internal_key = getattr(s, "INTERNAL_API_KEY", None)
    if internal_key is not None and (
        internal_key in _PLACEHOLDER_SECRETS or "change" in internal_key or len(internal_key) < 32
    ):
        problems.append("INTERNAL_API_KEY must be a random value of at least 32 characters")
    return problems


if settings.ENVIRONMENT == "production" and production_problems(settings):
    raise RuntimeError("Refusing to start in production: " + "; ".join(production_problems(settings)))
