from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Booking Service"
    SECRET_KEY: str = "change-in-production"
    ALGORITHM: str = "HS256"
    DATABASE_URL: str = "postgresql+asyncpg://alakh:alakh_secret@postgres:5432/booking_db"
    REDIS_URL: str = "redis://redis:6379/2"
    SHOP_SERVICE_URL: str = "http://shop_service:8000"
    SERVICE_CATALOG_URL: str = "http://service_catalog_service:8000"
    PRICING_ENGINE_URL: str = "http://pricing_engine:8000"
    NOTIFICATION_SERVICE_URL: str = "http://notification_service:8000"
    TRUST_RISK_SERVICE_URL: str = "http://trust_risk_service:8000"
    # Customers' display names ("Ravi S.") for the shop, and their numbers for masked calls.
    AUTH_SERVICE_URL: str = "http://auth_service:8000"
    # Shared with notification_service, trust_risk_service and auth_service; without it no notifications
    # or risk signals are sent, and shops see every customer as "Customer".
    INTERNAL_API_KEY: str = ""
    # Masked calls between a booking's customer and its shop through a telephony bridge, which rings both
    # from a virtual number so neither sees the other's. "none" (the default) leaves only the chat.
    CALL_PROVIDER: str = "none"
    # Exotel click-to-call (CALL_PROVIDER=exotel): API key and token, account SID, the virtual number
    # (ExoPhone) both sides see, and the API host of the account's region.
    EXOTEL_API_KEY: str = ""
    EXOTEL_API_TOKEN: str = ""
    EXOTEL_ACCOUNT_SID: str = ""
    EXOTEL_CALLER_ID: str = ""
    EXOTEL_SUBDOMAIN: str = "api.exotel.com"
    # Told when a booking is completed, cancelled or disputed (commission, refunds), over /internal.
    PAYMENT_SERVICE_URL: str = "http://payment_service:8000"
    # The background worker: booking reminders (24h and 1h before), expiring bookings the shop never
    # confirmed, and retrying what payment_service has not accepted yet. Off in tests (conftest.py).
    REMINDERS_ENABLED: bool = True
    WORKER_INTERVAL_SECONDS: float = 60
    # A PENDING booking the shop has not confirmed this long after it was made (or by its start time)
    # is cancelled and refunded.
    EXPIRE_PENDING_AFTER_HOURS: float = 12
    # This long after a completed visit the customer is asked once whether to book it again (0: never),
    # unless they already have; visits older than this plus REBOOK_REMINDER_WINDOW_DAYS are left alone.
    REBOOK_REMINDER_DAYS: int = 28
    REBOOK_REMINDER_WINDOW_DAYS: int = 14
    # Times in notifications are shown in this zone.
    DISPLAY_TIMEZONE: str = "Asia/Kolkata"
    # Browsers talk to the gateway, never to a service directly, so no cross-origin access by default.
    CORS_ORIGINS: List[str] = []
    # "production" turns on the checks at the bottom of this file.
    ENVIRONMENT: str = "development"

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
