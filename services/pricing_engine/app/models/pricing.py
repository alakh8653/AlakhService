import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Float, Integer, Text
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
