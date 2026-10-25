from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

MAX_MESSAGE_LENGTH = 1000


class MessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)

    @field_validator("body")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class MessageResponse(BaseModel):
    """A chat message as either party sees it: no ids, numbers or addresses of the other side."""

    id: str
    booking_id: str
    # customer, shop (its owner) or provider.
    sender_role: str
    # The customer's display name ("Ravi S."), or "Shop" / "Provider".
    sender_name: str
    is_mine: bool
    body: str
    # Contact details were hidden from this message.
    flagged: bool
    created_at: datetime
    # When the other side read it (null while unread).
    read_at: Optional[datetime] = None


class MessagePage(BaseModel):
    # Page 1 holds the newest messages; each page is oldest first, ready to show top to bottom.
    items: List[MessageResponse]
    total: int
    page: int
    per_page: int
    # Messages from the other side the caller has not marked read.
    unread: int
    # False once the chat is read-only (the booking closed more than the grace period ago), and for admins.
    can_send: bool
    # When a closed booking's chat turns read-only; null while the booking is open.
    open_until: Optional[datetime] = None
    # Whether POST /bookings/{id}/call can place a masked call; without it the apps show only the chat.
    calling_enabled: bool


class ReadReceipt(BaseModel):
    marked: int


class CallResponse(BaseModel):
    """The platform is ringing the caller; never the other party's number."""

    status: str
    call_id: str
    callee: Literal["customer", "shop", "provider"]
    message: str


class FlaggedMessage(BaseModel):
    """A message with contact details hidden, as admins review it (with what was written)."""

    id: str
    booking_id: str
    sender_id: str
    sender_role: str
    body: str
    original_body: Optional[str] = None
    flag_reasons: List[str]
    created_at: datetime


class FlaggedMessagePage(BaseModel):
    items: List[FlaggedMessage]
    total: int
    skip: int
    limit: int


class RepeatOffender(BaseModel):
    user_id: str
    sender_role: str
    attempts: int
    bookings: int
    last_attempt_at: datetime


class RepeatOffenderList(BaseModel):
    # People with at least min_attempts flagged messages.
    min_attempts: int
    items: List[RepeatOffender]
