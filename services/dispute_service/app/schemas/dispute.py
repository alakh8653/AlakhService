from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DisputeCreate(BaseModel):
    booking_id: str
    # Set from the caller's token; only admins may name someone else.
    raised_by: Optional[str] = None
    dispute_type: str = Field(min_length=1, max_length=50)
    description: str = Field(min_length=3, max_length=2000)
    evidence_urls: Optional[List[str]] = None

    @field_validator("booking_id")
    @classmethod
    def booking_id_is_uuid(cls, v: str) -> str:
        # booking_service ids are UUIDs; anything else would be spliced into its URL.
        return str(UUID(v))


class DisputeResolve(BaseModel):
    resolution: str
    # What happens to the money: all of it back to the customer, part of it (amount_cents), all of it
    # to the shop, or nothing (a dispute that is not about money).
    outcome: Literal["REFUND_FULL", "REFUND_PARTIAL", "RELEASE_TO_SHOP", "NO_ACTION"] = "NO_ACTION"
    amount_cents: Optional[int] = Field(default=None, gt=0)

    @model_validator(mode="after")
    def amount_only_for_partial(self):
        if self.outcome == "REFUND_PARTIAL" and self.amount_cents is None:
            raise ValueError("amount_cents is required for a partial refund")
        if self.outcome != "REFUND_PARTIAL" and self.amount_cents is not None:
            raise ValueError("amount_cents is only for a partial refund")
        return self


class DisputeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    booking_id: str
    raised_by: str
    dispute_type: str
    description: str
    status: str
    resolution: Optional[str] = None
    outcome: Optional[str] = None
    refund_amount_cents: Optional[int] = None
    evidence_urls: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None


class DisputeListResponse(BaseModel):
    data: List[DisputeResponse]
    total: int
    page: int
    per_page: int


class DisputeMessageCreate(BaseModel):
    author_id: str
    content: str


class DisputeMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    dispute_id: str
    author_id: str
    content: str
    created_at: datetime
