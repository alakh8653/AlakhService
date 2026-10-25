import re
from datetime import datetime, timezone


def validate_phone_number(v: str) -> str:
    """Validate a basic international phone number (digits, spaces, +, -, parens)."""
    cleaned = re.sub(r"[\s\-\(\)]", "", v)
    if not re.match(r"^\+?\d{7,15}$", cleaned):
        raise ValueError("Invalid phone number format")
    return v


def validate_password_strength(v: str) -> str:
    """Enforce minimum password requirements: 8+ chars, 1 uppercase, 1 digit."""
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters long")
    if not re.search(r"[A-Z]", v):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"\d", v):
        raise ValueError("Password must contain at least one digit")
    return v


def validate_future_datetime(v: datetime) -> datetime:
    """Ensure the datetime is in the future."""
    now = datetime.now(timezone.utc)
    if v.tzinfo is None:
        v = v.replace(tzinfo=timezone.utc)
    if v <= now:
        raise ValueError("Datetime must be in the future")
    return v


def validate_positive_amount(v: float) -> float:
    """Ensure the amount is strictly positive."""
    if v <= 0:
        raise ValueError("Amount must be greater than zero")
    return v
