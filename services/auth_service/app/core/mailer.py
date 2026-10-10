"""Outgoing email for account messages (password reset links)."""
from email.message import EmailMessage
from urllib.parse import urlencode

import aiosmtplib
import structlog

from app.config import settings

log = structlog.get_logger()


def password_reset_link(token: str) -> str:
    return f"{settings.PASSWORD_RESET_URL}?{urlencode({'token': token})}"


def password_reset_message(to_email: str, name: str, token: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = "Reset your AlakhService password"
    msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
    msg["To"] = to_email
    msg.set_content(
        f"Hi {name},\n\n"
        "Someone asked to reset the password for your AlakhService account. "
        f"Use this link within {settings.PASSWORD_RESET_EXPIRE_MINUTES} minutes:\n\n"
        f"{password_reset_link(token)}\n\n"
        "The link works once. If you did not ask for this, you can ignore this email; "
        "your password has not changed.\n"
    )
    return msg


async def send_password_reset(user_id: str, to_email: str, name: str, token: str) -> None:
    """Email a reset link. Runs after the response is sent, so failures are logged, not raised."""
    if not settings.SMTP_HOST:
        if settings.LOG_PASSWORD_RESET_TOKENS:
            log.warning("password_reset_token_for_local_testing", user_id=user_id, token=token)
        else:
            log.warning("password_reset_email_not_configured", user_id=user_id)
        return
    try:
        await aiosmtplib.send(
            password_reset_message(to_email, name, token),
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USERNAME or None,
            password=settings.SMTP_PASSWORD or None,
            start_tls=settings.SMTP_USE_TLS,
        )
        log.info("password_reset_email_sent", user_id=user_id)
    except Exception as exc:  # SMTP outages must not surface to the caller
        log.error("password_reset_email_failed", user_id=user_id, error=str(exc))
