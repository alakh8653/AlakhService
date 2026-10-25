import uuid

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from app.database import Base


class PriceCalculation(Base):
    __tablename__ = "price_calculations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    service_id = Column(String, nullable=False, index=True)
    customer_id = Column(String, nullable=False, index=True)
    base_price_cents = Column(Integer, nullable=False)
    final_price_cents = Column(Integer, nullable=False)
    applied_rules = Column(Text, nullable=True)  # JSON list
    demand_level = Column(Float, default=1.0, nullable=False)
    supply_level = Column(Float, default=1.0, nullable=False)
    # Coupon whose discount this quote includes; it is only used up when the quote is redeemed.
    coupon_code = Column(String, nullable=True)
    redeemed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Coupon(Base):
    __tablename__ = "coupons"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String, nullable=False, unique=True, index=True)
    discount_pct = Column(Float, nullable=False)
    max_uses = Column(Integer, nullable=True)
    uses_count = Column(Integer, default=0, nullable=False)
    valid_from = Column(DateTime(timezone=True), nullable=True)
    valid_to = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)


class CouponRedemption(Base):
    """A coupon used by a customer, at most once each."""

    __tablename__ = "coupon_redemptions"
    __table_args__ = (UniqueConstraint("coupon_id", "customer_id", name="uq_coupon_redemptions_coupon_customer"),)

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    coupon_id = Column(String, ForeignKey("coupons.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id = Column(String, nullable=False)
    calculation_id = Column(
        String, ForeignKey("price_calculations.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    redeemed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
