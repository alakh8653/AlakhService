from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Payment Service"
    SECRET_KEY: str = "change-in-production"
    ALGORITHM: str = "HS256"
    DATABASE_URL: str = "postgresql+asyncpg://alakh:alakh_secret@postgres:5432/payment_db"
    REDIS_URL: str = "redis://redis:6379/3"
    # Browsers talk to the gateway, never to a service directly, so no cross-origin access by default.
    CORS_ORIGINS: List[str] = []
    # "production" turns on the checks at the bottom of this file.
    ENVIRONMENT: str = "development"
    RAZORPAY_KEY_ID: Optional[str] = None
    RAZORPAY_KEY_SECRET: Optional[str] = None
    # Set in the Razorpay dashboard when adding the webhook; without it webhooks are refused.
    RAZORPAY_WEBHOOK_SECRET: Optional[str] = None
    PLATFORM_ACCOUNT_ID: str = "platform_account"
    BOOKING_SERVICE_URL: str = "http://booking_service:8000"
    SHOP_SERVICE_URL: str = "http://shop_service:8000"
    NOTIFICATION_SERVICE_URL: str = "http://notification_service:8000"
    TRUST_RISK_SERVICE_URL: str = "http://trust_risk_service:8000"
    # Refunds are recorded in admin_service's audit log.
    ADMIN_SERVICE_URL: str = "http://admin_service:8000"
    # Shared with notification, trust_risk and admin services; without it no notifications, risk
    # signals or audit reports are sent.
    INTERNAL_API_KEY: str = ""

    # extra="ignore": old .env files may still carry settings that are gone (e.g. STRIPE_*).
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


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
