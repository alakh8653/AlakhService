import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import true as sa_true
from sqlalchemy.sql import func

from app.database import Base


class ServiceCategory(Base):
    __tablename__ = "service_categories"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False, unique=True, index=True)
    parent_id = Column(String, ForeignKey("service_categories.id", ondelete="SET NULL"), nullable=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)


class ServiceListing(Base):
    __tablename__ = "service_listings"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    category_id = Column(String, ForeignKey("service_categories.id", ondelete="SET NULL"), nullable=True)
    shop_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    price_cents = Column(Integer, nullable=False)
    duration_minutes = Column(Integer, nullable=True)
    tags = Column(Text, nullable=True)  # JSON list
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # How the service can be delivered, comma-separated: AT_SHOP (the customer comes in),
    # AT_HOME (a provider visits) and/or PICKUP_DROP (the item is collected and brought back).
    service_modes = Column(String(100), default="AT_SHOP", server_default="AT_SHOP", nullable=False)
    # Added to the price when the customer chooses that mode.
    home_visit_fee_cents = Column(Integer, default=0, server_default="0", nullable=False)
    pickup_fee_cents = Column(Integer, default=0, server_default="0", nullable=False)
    # False while the shop awaits approval (or is switched off): kept out of browsing and search.
    # shop_service sets it when a shop is approved, rejected or switched on or off.
    shop_listed = Column(Boolean, default=True, server_default=sa_true(), nullable=False, index=True)


class ServiceTag(Base):
    __tablename__ = "service_tags"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, unique=True, index=True)
