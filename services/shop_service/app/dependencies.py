"""Caller identity forwarded by the API gateway.

The gateway verifies the access token and sets x-user-id / x-user-role, stripping any values a
client sent, so they can be trusted for requests that come through it.
"""
from dataclasses import dataclass
from typing import Optional

from fastapi import Header, HTTPException


@dataclass(frozen=True)
class Caller:
    user_id: str
    role: str

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def optional_caller(
    x_user_id: Optional[str] = Header(default=None), x_user_role: Optional[str] = Header(default=None)
) -> Optional[Caller]:
    return Caller(x_user_id, x_user_role or "user") if x_user_id else None


def require_caller(
    x_user_id: Optional[str] = Header(default=None), x_user_role: Optional[str] = Header(default=None)
) -> Caller:
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    return Caller(x_user_id, x_user_role or "user")


def ensure_owner(owner_id: str, caller: Caller) -> None:
    if not caller.is_admin and caller.user_id != owner_id:
        raise HTTPException(status_code=403, detail="Not your shop")
