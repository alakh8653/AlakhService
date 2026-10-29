from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Shop Service"
    DATABASE_URL: str = "postgresql+asyncpg://alakh:alakh_secret@postgres:5432/shop_db"
    REDIS_URL: str = "redis://redis:6379/0"
    # Browsers talk to the gateway, never to a service directly, so no cross-origin access by default.
    CORS_ORIGINS: List[str] = []
    # "production" turns on the checks at the bottom of this file.
    ENVIRONMENT: str = "development"
    SECRET_KEY: str = "change-in-production"
    ALGORITHM: str = "HS256"
    BOOKING_SERVICE_URL: str = "http://booking_service:8000"
    # Reviewers' public names (first name and last initial) come from their account.
    AUTH_SERVICE_URL: str = "http://auth_service:8000"
    # Shop approvals are reported to admin_service's audit log and the owner is told through
    # notification_service; both are best effort and skipped without INTERNAL_API_KEY.
    ADMIN_SERVICE_URL: str = "http://admin_service:8000"
    NOTIFICATION_SERVICE_URL: str = "http://notification_service:8000"
    # Told when a shop starts or stops being public, so its services show or hide in browsing.
    SERVICE_CATALOG_URL: str = "http://service_catalog_service:8000"
    # How often each shop's listing is sent to service_catalog again, in case a change was missed (0: never).
    LISTING_RESYNC_SECONDS: float = 600
    # Shared with the other services for /internal/... calls (payment_service reads payout details).
    INTERNAL_API_KEY: str = ""
    # KYC files uploaded through the API are kept here (mount a volume in production); empty turns
    # uploads off, and owners give https links to their documents instead.
    DOCUMENT_STORAGE_DIR: str = "/app/data/shop_documents"
    DOCUMENT_MAX_BYTES: int = 5 * 1024 * 1024
    MAX_DOCUMENTS_PER_SHOP: int = 20

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
