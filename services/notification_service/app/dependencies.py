"""Caller identity from the bearer access token.

Tokens are verified here rather than trusting gateway-set headers, because the service port can
be reached without going through the gateway.
"""
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import settings

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Caller:
    user_id: str
    role: str

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def caller_from_token(token: str) -> Caller:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from None
    # Refresh and single-purpose (e.g. password reset) tokens share the signing key; reject them.
    if not payload.get("sub") or payload.get("type") != "access" or "purpose" in payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return Caller(payload["sub"], payload.get("role") or "user")


def require_caller(credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer)) -> Caller:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return caller_from_token(credentials.credentials)


def require_admin(caller: Caller = Depends(require_caller)) -> Caller:
    if not caller.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return caller


def ensure_self_or_admin(user_id: str, caller: Caller) -> str:
    if user_id != caller.user_id and not caller.is_admin:
        raise HTTPException(status_code=403, detail="Not allowed for another user")
    return user_id


def target_user(user_id: Optional[str] = Query(None), caller: Caller = Depends(require_caller)) -> str:
    """The caller's own id; admins may name another user with ?user_id=."""
    return caller.user_id if user_id is None else ensure_self_or_admin(user_id, caller)
