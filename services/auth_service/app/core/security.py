import hashlib
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import bcrypt
from fastapi import Request
from jose import JWTError, jwt

from app.config import settings

# bcrypt only uses the first 72 bytes of a password; truncate explicitly (as passlib did)
# because bcrypt>=5 raises on longer input.
_BCRYPT_MAX_BYTES = 72


def _password_bytes(password: str) -> bytes:
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_password_bytes(password), bcrypt.gensalt()).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_password_bytes(plain), hashed.encode("ascii"))
    except ValueError:  # malformed or non-bcrypt hash
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    # iat to the millisecond: tokens issued before a sign-out are refused (see core/revocation.py).
    to_encode.update({"exp": expire, "iat": round(time.time(), 3), "type": "access", "jti": secrets.token_hex(16)})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh", "jti": secrets.token_hex(16)})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


PASSWORD_RESET_TYPE = "password_reset"


def _password_version(hashed_password: str) -> str:
    """Changes whenever the password does, so a reset token works at most once."""
    return hashlib.sha256(hashed_password.encode("ascii")).hexdigest()[:16]


def create_password_reset_token(user_id: str, hashed_password: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES)
    to_encode = {
        "sub": user_id,
        "type": PASSWORD_RESET_TYPE,
        "pwv": _password_version(hashed_password),
        "exp": expire,
        "jti": secrets.token_hex(16),
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def password_reset_token_matches(payload: dict, hashed_password: str) -> bool:
    return payload.get("type") == PASSWORD_RESET_TYPE and payload.get("pwv") == _password_version(hashed_password)


def is_access_token(payload: dict) -> bool:
    """Only access tokens authenticate API calls; refresh and single-purpose tokens do not."""
    return payload.get("type") == "access" and "purpose" not in payload


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError as e:
        raise ValueError(f"Invalid token: {e}") from e


def generate_otp() -> Tuple[str, str]:
    code = str(secrets.randbelow(1000000)).zfill(6)
    hashed = hashlib.sha256(code.encode()).hexdigest()
    return code, hashed


def verify_otp(plain_code: str, hashed_code: str) -> bool:
    return hashlib.sha256(plain_code.encode()).hexdigest() == hashed_code


def client_ip(request: Request) -> str:
    """The caller's address: the gateway puts it in X-Real-IP (overwriting anything the client sent)."""
    forwarded = (request.headers.get("x-real-ip") or "").strip()
    if forwarded:
        return forwarded[:64]
    return request.client.host if request.client else "unknown"


def describe_device(user_agent: Optional[str]) -> str:
    """A short, human description of a browser or app from its User-Agent, e.g. "Chrome on Windows"."""
    ua = user_agent or ""
    if "AlakhService" in ua or "Dart/" in ua or "okhttp" in ua:
        app = "Alakh app"
    elif "Edg/" in ua:
        app = "Edge"
    elif "Chrome/" in ua and "Chromium" not in ua:
        app = "Chrome"
    elif "Firefox/" in ua:
        app = "Firefox"
    elif "Safari/" in ua:
        app = "Safari"
    else:
        app = "Unknown browser"
    for marker, system in (
        ("Android", "Android"),
        ("iPhone", "iPhone"),
        ("iPad", "iPad"),
        ("Windows", "Windows"),
        ("Mac OS X", "Mac"),
        ("Linux", "Linux"),
    ):
        if marker in ua:
            return f"{app} on {system}"
    return app


def get_device_fingerprint(request: Request) -> str:
    user_agent = request.headers.get("user-agent", "")
    raw = f"{user_agent}:{client_ip(request)}"
    return hashlib.sha256(raw.encode()).hexdigest()


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
