from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Auth Service"
    SECRET_KEY: str = "change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    # Shared secret other platform services present on /internal routes (e.g. admin_service bans).
    INTERNAL_API_KEY: str = ""
    # Profile data erased when someone deletes their account.
    USER_SERVICE_URL: str = "http://user_service:8000"
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    DATABASE_URL: str = "postgresql+asyncpg://alakh:alakh_secret@postgres:5432/auth_db"
    REDIS_URL: str = "redis://redis:6379/0"
    # Browsers talk to the gateway, never to a service directly, so no cross-origin access by default.
    CORS_ORIGINS: List[str] = []
    # "production" turns on the checks at the bottom of this file.
    ENVIRONMENT: str = "development"
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_DURATION_SECONDS: int = 300
    OTP_EXPIRE_SECONDS: int = 300
    PASSWORD_RESET_EXPIRE_MINUTES: int = 30
    # Where the emailed link points; the token is appended as ?token=...
    PASSWORD_RESET_URL: str = "http://localhost:5173/reset-password"
    # Outgoing mail for password reset links. With no SMTP_HOST, no email is sent.
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True
    SMTP_FROM_EMAIL: str = "noreply@alakhservice.com"
    SMTP_FROM_NAME: str = "AlakhService"
    # Local testing only, when SMTP is not configured: log reset tokens instead of emailing them.
    # Never enable where logs are shared; a logged token lets its reader take over the account.
    LOG_PASSWORD_RESET_TOKENS: bool = False
    # SMS for one-time codes to phone numbers (Twilio REST API). Without these, no SMS is sent.
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = ""
    OTP_REQUESTS_PER_WINDOW: int = 3
    OTP_REQUEST_WINDOW_SECONDS: int = 600
    # Local testing only: log one-time codes when they cannot be delivered.
    LOG_OTP_CODES: bool = False

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
