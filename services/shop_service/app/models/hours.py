import uuid

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, false

from app.database import Base


class ShopScheduleSettings(Base):
    """Per-shop booking settings; the weekly intervals themselves are rows of shop_hours."""

    __tablename__ = "shop_schedule_settings"

    shop_id = Column(String, ForeignKey("shops.id", ondelete="CASCADE"), primary_key=True)
    # Set once the owner has saved a week, even an all-closed one: until then the shop takes bookings at
    # any future time, as before opening hours existed.
    hours_configured = Column(Boolean, default=False, server_default=false(), nullable=False)
    # How many customers can be served at once; null means one per active staff member.
    capacity = Column(Integer, nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=True)


class ShopHoliday(Base):
    """A date (in the shop's time zone) on which the shop is closed whatever its weekly hours say."""

    __tablename__ = "shop_holidays"
    __table_args__ = (UniqueConstraint("shop_id", "date", name="uq_shop_holidays_shop_date"),)

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    shop_id = Column(String, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    note = Column(String(120), nullable=True)
