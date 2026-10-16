from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from app.config import settings
from app.core.exceptions import CredentialsException

# bcrypt only uses the first 72 bytes of a password; truncate explicitly (as passlib did)
# because bcrypt>=5 raises on longer input.
_BCRYPT_MAX_BYTES = 72


def _password_bytes(password: str) -> bytes:
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True if the plain password matches the stored hash."""
    try:
        return bcrypt.checkpw(_password_bytes(plain_password), hashed_password.encode("ascii"))
    except ValueError:  # malformed or non-bcrypt hash
        return False


def get_password_hash(password: str) -> str:
    """Return the bcrypt hash of the given password."""
    return bcrypt.hashpw(_password_bytes(password), bcrypt.gensalt()).decode("ascii")


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """Create a short-lived JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict[str, Any]) -> str:
    """Create a long-lived JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str, expected_type: str = "access") -> dict[str, Any]:
    """Decode and validate a JWT of the given type. Raises CredentialsException on failure.

    Access and refresh tokens share the signing key, so the type claim is what stops a
    refresh token being used as an access token (and vice versa).
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError as exc:
        raise CredentialsException() from exc
    if payload.get("type") != expected_type:
        raise CredentialsException()
    return payload
