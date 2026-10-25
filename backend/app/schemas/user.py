import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class UserBase(BaseModel):
    email: EmailStr
    full_name: str | None = None
    phone_number: str | None = None


class UserCreate(UserBase):
    password: str


class UserRead(UserBase):
    id: uuid.UUID
    is_active: bool
    is_verified: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):
    full_name: str | None = None
    phone_number: str | None = None
    email: EmailStr | None = None


class UserInDB(UserBase):
    id: uuid.UUID
    hashed_password: str
    is_active: bool
    is_superuser: bool
    is_verified: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
