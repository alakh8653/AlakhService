"""Outgoing email and SMS for account messages (password reset links, one-time codes)."""

from email.message import EmailMessage
from urllib.parse import urlencode

import aiosmtplib
import structlog

from app.config import settings
from app.core import sms

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


async def _send_sms(to_number: str, body: str) -> None:
    """Text a one-time code through SMS_PROVIDER (MSG91 with the OTP's DLT template, or Twilio)."""
    await sms.send_sms(to_number, body, settings.MSG91_OTP_TEMPLATE_ID)


async def send_otp_code(user_id: str, destination: str, code: str, purpose: str) -> None:
    """Deliver a one-time code by email or SMS. Runs after the response; failures are logged."""
    minutes = max(1, settings.OTP_EXPIRE_SECONDS // 60)
    # The same words by email and SMS; for SMS they must match the DLT template (core/sms.py).
    text = sms.OTP_SMS_TEXT.format(code=code, minutes=minutes)
    by_email = "@" in destination
    configured = settings.SMTP_HOST if by_email else sms.configured()
    if not configured:
        if settings.LOG_OTP_CODES:
            log.warning("otp_code_for_local_testing", user_id=user_id, purpose=purpose, code=code)
        else:
            log.warning("otp_delivery_not_configured", user_id=user_id, channel="email" if by_email else "sms")
        return
    try:
        if by_email:
            msg = EmailMessage()
            msg["Subject"] = "Your AlakhService code"
            msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
            msg["To"] = destination
            msg.set_content(text + "\n")
            await aiosmtplib.send(
                msg,
                hostname=settings.SMTP_HOST,
                port=settings.SMTP_PORT,
                username=settings.SMTP_USERNAME or None,
                password=settings.SMTP_PASSWORD or None,
                start_tls=settings.SMTP_USE_TLS,
            )
        else:
            await _send_sms(destination, text)
        log.info("otp_delivered", user_id=user_id, channel="email" if by_email else "sms")
    except Exception as exc:  # delivery outages must not surface to the caller
        log.error("otp_delivery_failed", user_id=user_id, error=str(exc))
