import re
from datetime import datetime
from typing import Optional, Literal
from uuid import UUID
from pydantic import BaseModel, EmailStr, field_validator, ConfigDict


class UserCreate(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    password: str
    full_name: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not re.match(r"^\+[1-9]\d{1,14}$", v):
                raise ValueError("Phone must be in E.164 format (e.g. +919876543210)")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v

    @field_validator("email", "phone")
    @classmethod
    def at_least_one_contact(cls, v):
        return v

    def model_post_init(self, __context) -> None:
        if not self.email and not self.phone:
            raise ValueError("At least one of email or phone must be provided")


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class OTPRequest(BaseModel):
    phone_or_email: str
    purpose: Literal["registration", "login", "password_reset"]


class OTPVerify(BaseModel):
    phone_or_email: str
    code: str
    purpose: Literal["registration", "login", "password_reset"]


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: Optional[str] = None
    phone: Optional[str] = None
    full_name: str
    is_active: bool
    is_verified: bool
    role: str
    created_at: datetime
