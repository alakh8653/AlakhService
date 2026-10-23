import uuid

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, false
from sqlalchemy.sql import func

from app.database import Base

PENDING_REVIEW = "PENDING_REVIEW"
APPROVED = "APPROVED"
REJECTED = "REJECTED"
VERIFICATION_STATUSES = (PENDING_REVIEW, APPROVED, REJECTED)


class Shop(Base):
    __tablename__ = "shops"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    rating_avg = Column(Float, default=0.0, nullable=False)
    rating_count = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    city = Column(String, nullable=True, index=True)
    address = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # KYC: a new shop is hidden from customers until an admin approves it (is_verified mirrors APPROVED).
    verification_status = Column(
        String(20), nullable=False, default=PENDING_REVIEW, server_default=PENDING_REVIEW, index=True
    )
    rejection_reason = Column(Text, nullable=True)
    # The registered business, as printed on tax invoices.
    legal_name = Column(String(200), nullable=True)
    legal_address = Column(Text, nullable=True)
    gstin = Column(String(15), nullable=True)
    # Set when the owner submits for review; the admin queue is ordered by it.
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by = Column(String, nullable=True)


class ShopDocument(Base):
    __tablename__ = "shop_documents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    shop_id = Column(String, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String, nullable=False)
    # An https link the owner gave, or the API path of a file uploaded here (storage_key set).
    url = Column(String, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    # Uploaded files only: where the bytes are in DOCUMENT_STORAGE_DIR, and what they are.
    storage_key = Column(String, nullable=True)
    file_name = Column(String(255), nullable=True)
    content_type = Column(String(100), nullable=True)
    size_bytes = Column(Integer, nullable=True)
    uploaded_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True)


class ShopPayoutDetails(Base):
    """Where the platform pays a shop's earnings: a bank account or a UPI id (one row per shop)."""

    __tablename__ = "shop_payout_details"

    shop_id = Column(String, ForeignKey("shops.id", ondelete="CASCADE"), primary_key=True)
    method = Column(String(10), nullable=False)  # BANK or UPI
    account_name = Column(String(200), nullable=True)
    account_number = Column(String(18), nullable=True)
    ifsc = Column(String(11), nullable=True)
    upi_id = Column(String(255), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=True)
    updated_by = Column(String, nullable=True)


class ShopHours(Base):
    __tablename__ = "shop_hours"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    shop_id = Column(String, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False, index=True)
    day_of_week = Column(Integer, nullable=False)  # 0=Monday, 6=Sunday
    open_time = Column(String, nullable=False)  # "HH:MM"
    close_time = Column(String, nullable=False)  # "HH:MM"


class StaffMember(Base):
    __tablename__ = "staff_members"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    shop_id = Column(String, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, nullable=True, index=True)  # platform account, when the staff member has one
    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    role = Column(String, nullable=False, default="staff")
    service_ids = Column(Text, nullable=False, default="[]")  # JSON list of service listing ids
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ShopRating(Base):
    """One customer rating per completed booking; shops.rating_avg/rating_count aggregate these."""

    __tablename__ = "shop_ratings"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    shop_id = Column(String, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False, index=True)
    booking_id = Column(String, nullable=False, unique=True)
    customer_id = Column(String, nullable=False, index=True)
    service_id = Column(String, nullable=True, index=True)  # the booked service; unknown for older ratings
    # Shown publicly: first name and last initial only ("Priya S."), never the full name or contacts.
    reviewer_name = Column(String, nullable=True)
    rating = Column(Float, nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # The shop owner's one public reply, editable.
    reply = Column(Text, nullable=True)
    reply_created_at = Column(DateTime(timezone=True), nullable=True)
    reply_updated_at = Column(DateTime(timezone=True), nullable=True)
    # Reported reviews stay up until an admin hides them; hidden ones leave the shop's average too.
    report_count = Column(Integer, nullable=False, default=0, server_default="0")
    is_hidden = Column(Boolean, nullable=False, default=False, server_default=false())


class ReviewReport(Base):
    """A signed-in user flagging a review for moderation; one report per user per review."""

    __tablename__ = "review_reports"
    __table_args__ = (UniqueConstraint("review_id", "reporter_id", name="uq_review_reports_review_reporter"),)

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    review_id = Column(String, ForeignKey("shop_ratings.id", ondelete="CASCADE"), nullable=False, index=True)
    reporter_id = Column(String, nullable=False)
    reason = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
