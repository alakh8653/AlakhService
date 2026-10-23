"""Text messages for one-time codes: Twilio or MSG91, chosen with SMS_PROVIDER (twilio, msg91, none).

Indian networks deliver commercial SMS only from a DLT-registered sender id and template (TRAI).
MSG91 sends each message with its DLT template id; the text must match the registered template
word for word, with the variable parts (the code, the minutes) where the template has {#var#}.
"""

from typing import Optional

import httpx
import structlog

from app.config import settings

log = structlog.get_logger()

# Register this exact text as the DLT template for MSG91_OTP_TEMPLATE_ID:
#   Your AlakhService code is {#var#}. It expires in {#var#} minutes. Never share it.
OTP_SMS_TEXT = "Your AlakhService code is {code}. It expires in {minutes} minutes. Never share it."


def provider() -> str:
    return (settings.SMS_PROVIDER or "none").strip().lower()


def configured() -> bool:
    """Whether a one-time code can be texted at all with the current settings."""
    name = provider()
    if name == "twilio":
        return bool(settings.TWILIO_ACCOUNT_SID and settings.TWILIO_FROM_NUMBER)
    if name == "msg91":
        return bool(settings.MSG91_AUTH_KEY and settings.MSG91_SENDER_ID and settings.MSG91_OTP_TEMPLATE_ID)
    return False


async def send_twilio(to_number: str, body: str, transport: Optional[httpx.AsyncBaseTransport] = None) -> None:
    url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json"
    async with httpx.AsyncClient(timeout=10.0, transport=transport) as client:
        resp = await client.post(
            url,
            data={"To": to_number, "From": settings.TWILIO_FROM_NUMBER, "Body": body},
            auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
        )
    resp.raise_for_status()


async def send_msg91(
    to_number: str, body: str, template_id: str, transport: Optional[httpx.AsyncBaseTransport] = None
) -> None:
    """MSG91's send-SMS API with the sender id and the message's DLT template id."""
    async with httpx.AsyncClient(timeout=10.0, transport=transport) as client:
        resp = await client.post(
            settings.MSG91_API_URL,
            json={
                "sender": settings.MSG91_SENDER_ID,
                "route": "4",  # transactional
                "country": "91",
                "DLT_TE_ID": template_id,
                # MSG91 takes numbers with the country code and no "+".
                "sms": [{"message": body, "to": [to_number.lstrip("+")]}],
            },
            headers={"authkey": settings.MSG91_AUTH_KEY},
        )
    resp.raise_for_status()
    # MSG91 answers 200 with {"type": "error"} for some refusals (a bad template, no balance).
    try:
        if resp.json().get("type") == "error":
            raise RuntimeError(f"MSG91 refused the message: {resp.json().get('message')}")
    except ValueError:
        pass


async def send_sms(to_number: str, body: str, template_id: str) -> None:
    """Text [body] through the configured provider; [template_id] is its DLT template (MSG91)."""
    name = provider()
    if name == "msg91":
        await send_msg91(to_number, body, template_id)
    elif name == "twilio":
        await send_twilio(to_number, body)
    else:
        raise RuntimeError(f"SMS provider {name!r} cannot send messages")
