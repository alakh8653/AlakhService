import uuid
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base

class ServiceCategory(Base):
    __tablename__ = "service_categories"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    icon_url = Column(String, nullable=True)
    parent_id = Column(String, ForeignKey("service_categories.id", ondelete="SET NULL"), nullable=True, index=True)
    order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)
    children = relationship("ServiceCategory", backref="parent", foreign_keys=[parent_id], lazy="select")
    services = relationship("ServiceItem", back_populates="category", lazy="select")

class ServiceItem(Base):
    __tablename__ = "service_items"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    category_id = Column(String, ForeignKey("service_categories.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    base_price_cents = Column(Integer, nullable=False, default=0)
    currency = Column(String, default="INR", nullable=False)
    duration_minutes = Column(Integer, nullable=False, default=60)
    is_active = Column(Boolean, default=True, nullable=False)
    is_featured = Column(Boolean, default=False, nullable=False)
    booking_count = Column(Integer, default=0, nullable=False)
    metadata_json = Column("metadata", Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)
    category = relationship("ServiceCategory", back_populates="services")
    pricing_tiers = relationship("PricingTier", back_populates="service", cascade="all, delete-orphan")
    media = relationship("ServiceMedia", back_populates="service", cascade="all, delete-orphan", order_by="ServiceMedia.order")
    variants = relationship("ServiceVariant", back_populates="service", cascade="all, delete-orphan")

class PricingTier(Base):
    __tablename__ = "pricing_tiers"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    service_id = Column(String, ForeignKey("service_items.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    price_cents = Column(Integer, nullable=False)
    features = Column(Text, nullable=True)
    is_popular = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    service = relationship("ServiceItem", back_populates="pricing_tiers")

class ServiceMedia(Base):
    __tablename__ = "service_media"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    service_id = Column(String, ForeignKey("service_items.id", ondelete="CASCADE"), nullable=False, index=True)
    media_type = Column(String, nullable=False)
    url = Column(String, nullable=False)
    alt_text = Column(String, nullable=True)
    order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    service = relationship("ServiceItem", back_populates="media")

class ServiceVariant(Base):
    __tablename__ = "service_variants"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    service_id = Column(String, ForeignKey("service_items.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    price_modifier_cents = Column(Integer, default=0, nullable=False)
    duration_modifier_minutes = Column(Integer, default=0, nullable=False)
    is_available = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    service = relationship("ServiceItem", back_populates="variants")
