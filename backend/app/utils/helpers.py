import re
import uuid
from datetime import datetime


def generate_uuid() -> str:
    """Return a new random UUID as a string."""
    return str(uuid.uuid4())


def paginate(query, skip: int, limit: int):
    """Apply offset/limit pagination to a SQLAlchemy query."""
    return query.offset(skip).limit(limit)


def format_datetime(dt: datetime) -> str:
    """Return an ISO 8601 string representation of the given datetime."""
    return dt.isoformat()


def slugify(text: str) -> str:
    """Convert a text string to a URL-friendly slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    text = re.sub(r"^-+|-+$", "", text)
    return text


def truncate_string(s: str, max_len: int) -> str:
    """Return the string truncated to max_len characters, with ellipsis if needed."""
    if len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."
