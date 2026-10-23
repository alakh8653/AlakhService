from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from app.core.kyc import (
    mask_account_number,
    normalise_account_number,
    normalise_gstin,
    normalise_ifsc,
    normalise_upi,
)

DOCUMENT_TYPES = ("PAN", "GST", "AADHAAR", "UDYAM", "BANK_PROOF", "SHOP_PHOTO")
DocumentType = Literal["PAN", "GST", "AADHAAR", "UDYAM", "BANK_PROOF", "SHOP_PHOTO"]
VerificationStatus = Literal["PENDING_REVIEW", "APPROVED", "REJECTED"]


def valid_gstin(value: Optional[str]) -> Optional[str]:
    return normalise_gstin(value)


def blank_to_none(value: Optional[str]) -> Optional[str]:
    return (value or "").strip() or None


def not_null(value):
    """For partial updates of a column that always has a value: leave it out to keep it, but not null."""
    if value is None:
        raise ValueError("may be omitted but not null")
    return value


class ShopCreate(BaseModel):
    owner_id: str
    name: str
    category: str
    description: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    # KYC details; they can also be filled in later, before submitting for review.
    legal_name: Optional[str] = Field(default=None, max_length=200)
    legal_address: Optional[str] = Field(default=None, max_length=500)
    gstin: Optional[str] = None

    _gstin = field_validator("gstin")(valid_gstin)
    _blank = field_validator("legal_name", "legal_address")(blank_to_none)


class ShopUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_active: Optional[bool] = None
    legal_name: Optional[str] = Field(default=None, max_length=200)
    legal_address: Optional[str] = Field(default=None, max_length=500)
    gstin: Optional[str] = None

    # Only for a value sent explicitly (defaults are not validated); null clears the other fields.
    _required = field_validator("name", "category", "is_active")(not_null)
    _gstin = field_validator("gstin")(valid_gstin)
    _blank = field_validator("legal_name", "legal_address")(blank_to_none)


class ShopResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    owner_id: str
    name: str
    category: str
    description: Optional[str] = None
    rating_avg: float
    rating_count: int
    is_active: bool
    is_verified: bool
    city: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    created_at: datetime
    verification_status: VerificationStatus = "PENDING_REVIEW"
    rejection_reason: Optional[str] = None
    # The legal details are for the owner and admins only (blanked for everyone else, like the contacts).
    legal_name: Optional[str] = None
    legal_address: Optional[str] = None
    gstin: Optional[str] = None
    submitted_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None

    # What the apps show next to a shop ("4.6 (128)"), so lists need no extra call per shop.
    @computed_field
    @property
    def average_rating(self) -> float:
        return round(self.rating_avg, 1) if self.rating_count else 0.0

    @computed_field
    @property
    def review_count(self) -> int:
        return self.rating_count


class ShopDocumentCreate(BaseModel):
    """A document the owner keeps elsewhere (e.g. a DigiLocker or drive link): https links only."""

    type: DocumentType
    url: str = Field(min_length=12, max_length=1000, pattern=r"^https://\S+$")
    file_name: Optional[str] = Field(default=None, max_length=255)


class ShopDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    shop_id: str
    type: str
    url: str
    is_verified: bool
    file_name: Optional[str] = None
    content_type: Optional[str] = None
    size_bytes: Optional[int] = None
    created_at: Optional[datetime] = None
    # Set for a file stored here, which is downloaded through the API with the caller's token.
    storage_key: Optional[str] = Field(default=None, exclude=True)

    @computed_field
    @property
    def uploaded(self) -> bool:
        return bool(self.storage_key)


class ReviewDecision(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)

    @field_validator("reason", mode="before")
    @classmethod
    def _strip(cls, value):
        return value.strip() if isinstance(value, str) else value


class ShopReviewItem(ShopResponse):
    """A shop as the admin reviews it, with its documents."""

    documents: List[ShopDocumentResponse] = []
    has_payout_details: bool = False


class AdminShopList(BaseModel):
    items: List[ShopResponse]
    total: int


class PayoutDetailsIn(BaseModel):
    method: Literal["BANK", "UPI"]
    account_name: Optional[str] = Field(default=None, max_length=200)
    account_number: Optional[str] = None
    ifsc: Optional[str] = None
    upi_id: Optional[str] = None

    @field_validator("account_number")
    @classmethod
    def _account(cls, value):
        return normalise_account_number(value)

    @field_validator("ifsc")
    @classmethod
    def _ifsc(cls, value):
        return normalise_ifsc(value)

    @field_validator("upi_id")
    @classmethod
    def _upi(cls, value):
        return normalise_upi(value)

    _name = field_validator("account_name")(blank_to_none)

    @model_validator(mode="after")
    def _complete(self):
        if self.method == "BANK":
            missing = [f for f in ("account_name", "account_number", "ifsc") if not getattr(self, f)]
            if missing:
                raise ValueError(f"Bank payouts need {', '.join(missing)}")
            self.upi_id = None
        else:
            if not self.upi_id:
                raise ValueError("UPI payouts need upi_id")
            self.account_number = None
            self.ifsc = None
        return self


class PayoutDetailsOut(BaseModel):
    """Payout details as the public API shows them: the account number is masked."""

    model_config = ConfigDict(from_attributes=True)

    shop_id: str
    method: str
    account_name: Optional[str] = None
    account_number: Optional[str] = None
    ifsc: Optional[str] = None
    upi_id: Optional[str] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def masked(cls, details) -> "PayoutDetailsOut":
        view = cls.model_validate(details)
        return view.model_copy(update={"account_number": mask_account_number(view.account_number)})


class InternalShopResponse(ShopResponse):
    """The whole record for other services (invoices need the legal name, address and GSTIN)."""

    reviewed_by: Optional[str] = None


class ShopHoursCreate(BaseModel):
    shop_id: str
    day_of_week: int
    open_time: str
    close_time: str


class ShopHoursResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    shop_id: str
    day_of_week: int
    open_time: str
    close_time: str


class RatingUpdate(BaseModel):
    rating: float = Field(ge=1.0, le=5.0)


class ShopRatingCreate(BaseModel):
    booking_id: str
    # Whole stars (4.0 is accepted as 4); the written review is optional.
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("comment")
    @classmethod
    def blank_is_none(cls, value: Optional[str]) -> Optional[str]:
        return (value or "").strip() or None


class StaffCreate(BaseModel):
    shop_id: str
    name: str = Field(min_length=1, max_length=120)
    email: Optional[str] = None
    phone: Optional[str] = None
    role: str = "staff"
    user_id: Optional[str] = None
    service_ids: List[str] = []


class StaffUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    email: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    user_id: Optional[str] = None
    service_ids: Optional[List[str]] = None
    is_active: Optional[bool] = None

    # null service_ids means none; the other fields always have a value.
    _required = field_validator("name", "role", "is_active")(not_null)


class StaffResponse(BaseModel):
    id: str
    shop_id: str
    user_id: Optional[str] = None
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    role: str
    service_ids: List[str]
    is_active: bool
    created_at: datetime
