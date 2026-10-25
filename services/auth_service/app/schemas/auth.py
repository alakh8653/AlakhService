import re
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def check_password_strength(v: str) -> str:
    """The password policy, shared by registration and password reset."""
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters long")
    if not any(c.isupper() for c in v):
        raise ValueError("Password must contain at least one uppercase letter")
    if not any(c.isdigit() for c in v):
        raise ValueError("Password must contain at least one digit")
    return v


def lower_email(v):
    """Emails are matched without regard to case: Ravi@Example.com and ravi@example.com are one account."""
    return v.strip().lower() if isinstance(v, str) and "@" in v else v


class UserCreate(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    password: str
    full_name: str
    # The Terms and Privacy Policy version shown to the person (GET /legal/current). Required by the
    # register endpoint, which answers 422 "Please accept the Terms and Privacy Policy" without it.
    accepted_terms_version: Optional[str] = Field(None, max_length=32)

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
        return check_password_strength(v)

    _lower = field_validator("email")(lower_email)

    @field_validator("email", "phone")
    @classmethod
    def at_least_one_contact(cls, v):
        return v

    def model_post_init(self, __context) -> None:
        if not self.email and not self.phone:
            raise ValueError("At least one of email or phone must be provided")


class UserLogin(BaseModel):
    """Sign in with the account's email or phone number."""

    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    password: str

    _lower = field_validator("email")(lower_email)

    def model_post_init(self, __context) -> None:
        if not self.email and not self.phone:
            raise ValueError("Provide an email or a phone number")

    @property
    def identifier(self) -> str:
        return self.email or self.phone or ""


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class OTPRequest(BaseModel):
    phone_or_email: str
    # delete_account: the code is then confirmed at /auth/delete-account/otp, not /auth/verify-otp.
    purpose: Literal["registration", "login", "password_reset", "delete_account"]

    _lower = field_validator("phone_or_email")(lower_email)


class OTPVerify(BaseModel):
    phone_or_email: str
    code: str
    purpose: Literal["registration", "login", "password_reset"]

    _lower = field_validator("phone_or_email")(lower_email)


class AccountDeletionByOTP(BaseModel):
    """Deleting an account without signing in (the web page for app-store deletion requests)."""

    phone_or_email: str = Field(min_length=3, max_length=254)
    code: str = Field(min_length=4, max_length=10)

    _lower = field_validator("phone_or_email")(lower_email)

    @property
    def purpose(self) -> str:
        return "delete_account"


class AcceptTerms(BaseModel):
    accepted_terms_version: str = Field(min_length=1, max_length=32)


class LegalInfo(BaseModel):
    terms_version: str
    privacy_url: str
    terms_url: str
    refund_url: str
    grievance_url: str


class OTPVerifyResponse(BaseModel):
    """What a verified code grants: tokens for 'login', a reset token for 'password_reset'."""

    message: str
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: Optional[str] = None
    expires_in: Optional[int] = None
    reset_token: Optional[str] = None


class PasswordResetRequest(BaseModel):
    email: EmailStr

    _lower = field_validator("email")(lower_email)


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return check_password_strength(v)


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
    accepted_terms_version: Optional[str] = None
    accepted_terms_at: Optional[datetime] = None


class SessionResponse(BaseModel):
    """A device the account is signed in on."""

    id: str
    device: str
    ip_address: Optional[str] = None
    signed_in_at: datetime
    last_active_at: datetime
    current: bool = False
