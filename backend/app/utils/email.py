import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from app.config import settings

logger = logging.getLogger(__name__)


async def send_email(to_email: str, subject: str, html_body: str) -> None:
    """Send an HTML email using the configured SMTP settings (non-blocking)."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.EMAILS_FROM_EMAIL
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            start_tls=True,
        )
        logger.info("Email sent to %s | subject: %s", to_email, subject)
    except Exception as exc:
        logger.error("Failed to send email to %s: %s", to_email, exc)
        raise


async def send_verification_email(to_email: str, token: str) -> None:
    """Send an account verification email with the provided token."""
    subject = f"Verify your {settings.APP_NAME} account"
    html_body = f"""
    <h2>Welcome to {settings.APP_NAME}!</h2>
    <p>Click the link below to verify your email address:</p>
    <a href="http://localhost:8000/api/v1/auth/verify?token={token}">Verify Email</a>
    """
    await send_email(to_email, subject, html_body)


async def send_password_reset_email(to_email: str, token: str) -> None:
    """Send a password reset email with the provided token."""
    subject = f"Reset your {settings.APP_NAME} password"
    html_body = f"""
    <h2>Password Reset Request</h2>
    <p>Use the link below to reset your password. This link expires in 30 minutes.</p>
    <a href="http://localhost:8000/api/v1/auth/reset-password?token={token}">Reset Password</a>
    <p>If you did not request this, please ignore this email.</p>
    """
    await send_email(to_email, subject, html_body)


async def send_booking_confirmation_email(to_email: str, booking_details: dict) -> None:
    """Send a booking confirmation email with booking details."""
    subject = f"Booking Confirmed - {settings.APP_NAME}"
    html_body = f"""
    <h2>Your booking is confirmed!</h2>
    <p><strong>Service:</strong> {booking_details.get('service_name', 'N/A')}</p>
    <p><strong>Scheduled At:</strong> {booking_details.get('scheduled_at', 'N/A')}</p>
    <p><strong>Amount:</strong> ₹{booking_details.get('total_amount', 'N/A')}</p>
    <p>Thank you for choosing {settings.APP_NAME}!</p>
    """
    await send_email(to_email, subject, html_body)
