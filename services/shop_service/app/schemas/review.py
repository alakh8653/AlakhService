"""Reviews as customers see them, owner replies, reports and moderation."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


def _trimmed(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("must not be blank")
    return value


class StarCount(BaseModel):
    stars: int
    count: int


class RatingSummary(BaseModel):
    shop_id: str
    service_id: Optional[str] = None
    average_rating: float  # to one decimal; 0.0 when there are no ratings yet
    review_count: int
    distribution: List[StarCount]  # 5 stars first, every star level present


class ShopRatingBrief(BaseModel):
    shop_id: str
    average_rating: float
    review_count: int


class OwnerReply(BaseModel):
    text: str
    created_at: datetime
    updated_at: datetime


class ReviewResponse(BaseModel):
    """A review as anyone may see it: no customer id, full name or contact details."""

    id: str
    shop_id: str
    service_id: Optional[str] = None
    rating: int
    comment: Optional[str] = None
    reviewer_name: str
    created_at: datetime
    reply: Optional[OwnerReply] = None


class ReviewPage(BaseModel):
    items: List[ReviewResponse]
    total: int
    skip: int
    limit: int


class ReplyCreate(BaseModel):
    text: str = Field(min_length=1, max_length=1000)

    _trim = field_validator("text")(_trimmed)


class ReportCreate(BaseModel):
    reason: str = Field(min_length=3, max_length=500)

    _trim = field_validator("reason")(_trimmed)


class VisibilityUpdate(BaseModel):
    hidden: bool


class ModerationReview(ReviewResponse):
    """A review in the admin queue, with its moderation state and reports."""

    is_hidden: bool
    report_count: int
    report_reasons: List[str]


class ModerationPage(BaseModel):
    items: List[ModerationReview]
    total: int
    skip: int
    limit: int
