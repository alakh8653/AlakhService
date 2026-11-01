import uuid

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.sql import func

from app.database import Base

# What a payment is for: the booking itself, or a tip the customer adds once it is completed.
BOOKING, TIP, PACKAGE = "BOOKING", "TIP", "PACKAGE"


class Account(Base):
    __tablename__ = "accounts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id = Column(String, nullable=False, index=True)
    owner_type = Column(String, nullable=False)  # user, provider, platform
    balance_cents = Column(Integer, default=0, nullable=False)
    currency = Column(String, default="INR", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = Column(String, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    entry_type = Column(String, nullable=False)  # DEBIT or CREDIT
    amount_cents = Column(Integer, nullable=False)
    currency = Column(String, nullable=False)
    description = Column(String, nullable=False)
    reference_id = Column(String, nullable=True)
    reference_type = Column(String, nullable=True)
    running_balance = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)


class Payment(Base):
    __tablename__ = "payments"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id = Column(String, nullable=False, index=True)
    payer_id = Column(String, nullable=False, index=True)
    payee_id = Column(String, nullable=False)
    # The booking's shop (payee_id is its owner); earnings and payouts are kept per shop.
    shop_id = Column(String, nullable=True, index=True)
    amount_cents = Column(Integer, nullable=False)
    currency = Column(String, default="INR", nullable=False)
    status = Column(String, default="PENDING", nullable=False)
    payment_method = Column(String, nullable=False)
    provider_payment_id = Column(String, nullable=True)
    provider_order_id = Column(String, nullable=True, index=True)
    gateway = Column(String, nullable=True)  # razorpay, cash
    # BOOKING or TIP: a booking is paid for once, and tipped at most once, each on its own. PACKAGE: a
    # prepaid package of visits, whose booking_id holds the PackagePurchase id it pays for.
    purpose = Column(String(10), nullable=False, default=BOOKING, server_default=BOOKING)
    idempotency_key = Column(String, unique=True, nullable=False)
    metadata_json = Column("metadata", Text, nullable=True)
    # Numbered when the payment completes, gap-free per financial year: ALK/2026-27/000123.
    invoice_number = Column(String, nullable=True)
    invoice_issued_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)

    # A booking is paid for (and tipped) once, even if two checkouts are confirmed at the same moment.
    __table_args__ = (
        Index(
            "uq_payments_booking_purpose_completed",
            "booking_id",
            "purpose",
            unique=True,
            sqlite_where=text("status = 'COMPLETED'"),
            postgresql_where=text("status = 'COMPLETED'"),
        ),
        UniqueConstraint("invoice_number", name="uq_payments_invoice_number"),
    )


class Escrow(Base):
    __tablename__ = "escrows"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    payment_id = Column(String, ForeignKey("payments.id", ondelete="CASCADE"), nullable=False, index=True)
    booking_id = Column(String, nullable=False)
    amount_cents = Column(Integer, nullable=False)
    currency = Column(String, nullable=False)
    status = Column(String, default="CREATED", nullable=False)
    held_at = Column(DateTime(timezone=True), nullable=False)
    released_at = Column(DateTime(timezone=True), nullable=True)


class Refund(Base):
    __tablename__ = "refunds"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    payment_id = Column(String, ForeignKey("payments.id", ondelete="CASCADE"), nullable=False, index=True)
    amount_cents = Column(Integer, nullable=False)
    reason = Column(String, nullable=False)
    status = Column(String, default="PENDING", nullable=False)
    gateway_refund_id = Column(String, nullable=True)
    # Set by automatic refunds (cancel:{booking_id}, dispute:{dispute_id}) so a retried call refunds once.
    idempotency_key = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_refunds_idempotency_key"),)


class CommissionRate(Base):
    """An admin's commission rate for one shop, or for every shop without its own (shop_id "*")."""

    __tablename__ = "commission_rates"

    shop_id = Column(String, primary_key=True)
    commission_percent = Column(Numeric(5, 2), nullable=False)
    updated_by = Column(String, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)


class InvoiceSequence(Base):
    """The last invoice number used in a series (one series per financial year)."""

    __tablename__ = "invoice_sequences"

    series = Column(String, primary_key=True)
    last_number = Column(Integer, nullable=False, default=0)


class ShopEarning(Base):
    """What one booking earned its shop, after the platform's commission and GST on that commission.

    SALE is the booking itself (one per booking); ADJUSTMENT corrects a SALE already paid out (a later
    refund), so the difference is netted against the shop's next payout. TIP is a tip the customer paid
    online for its provider: no commission or GST, all of it paid out (TIP_ADJUSTMENT corrects one already
    paid out).

    ONLINE: the platform collected the money and owes the shop ``net`` (payout_cents = net).
    CASH: the shop collected it and owes the platform commission + GST (payout_cents is negative).
    """

    __tablename__ = "shop_earnings"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id = Column(String, nullable=False, index=True)
    kind = Column(String(20), nullable=False, default="SALE")
    payment_id = Column(String, nullable=True)
    shop_id = Column(String, nullable=False, index=True)
    collection = Column(String(10), nullable=False)  # ONLINE or CASH
    currency = Column(String, nullable=False, default="INR")
    gross_cents = Column(Integer, nullable=False)
    commission_percent = Column(Numeric(5, 2), nullable=False)
    gst_percent = Column(Numeric(5, 2), nullable=False)
    commission_cents = Column(Integer, nullable=False)
    gst_cents = Column(Integer, nullable=False)
    net_cents = Column(Integer, nullable=False)
    payout_cents = Column(Integer, nullable=False)
    status = Column(String(10), nullable=False)  # HELD, READY, PAID, REFUNDED
    # TIP: the staff member who did the job; the shop passes the tip on to them in full.
    provider_id = Column(String, nullable=True)
    # Paid by the platform for the customer's points: the shop earns as if the customer paid it.
    platform_discount_cents = Column(Integer, nullable=False, default=0, server_default="0")
    payout_id = Column(String, ForeignKey("payouts.id"), nullable=True, index=True)
    completed_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("booking_id", "kind", name="uq_shop_earnings_booking_kind"),)


class Payout(Base):
    """Money paid to a shop for a period, made by an admin batch and marked paid once transferred."""

    __tablename__ = "payouts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    batch_id = Column(String, nullable=False, index=True)
    shop_id = Column(String, nullable=False, index=True)
    period_from = Column(Date, nullable=True)
    period_to = Column(Date, nullable=False)
    amount_cents = Column(Integer, nullable=False)
    currency = Column(String, nullable=False, default="INR")
    status = Column(String(10), nullable=False, default="PENDING")  # PENDING, PAID
    paid_at = Column(DateTime(timezone=True), nullable=True)
    reference = Column(String, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)


class LoyaltyEntry(Base):
    """One change to a customer's points: earned on a completed booking, spent on (or returned from) a
    booking, a referral bonus, or taken back after a refund. The balance is their sum.

    The platform pays for points: a booking paid partly with points earns its shop the full price.
    """

    __tablename__ = "loyalty_entries"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    kind = Column(String(20), nullable=False)  # EARN, REDEEM, REDEEM_RETURN, REFERRAL_BONUS, CLAWBACK
    points = Column(Integer, nullable=False)  # positive adds, negative spends
    booking_id = Column(String, nullable=True, index=True)
    note = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)

    # Each event happens once per booking and person, however often it is reported.
    __table_args__ = (UniqueConstraint("user_id", "kind", "booking_id", name="uq_loyalty_user_kind_booking"),)


class ReferralCode(Base):
    """A customer's own code to invite friends."""

    __tablename__ = "referral_codes"

    user_id = Column(String, primary_key=True)
    code = Column(String(12), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)


class Referral(Base):
    """Who invited a new customer; both get a bonus once that customer's first booking is completed."""

    __tablename__ = "referrals"

    referee_id = Column(String, primary_key=True)
    referrer_id = Column(String, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    rewarded_at = Column(DateTime(timezone=True), nullable=True)
    rewarded_booking_id = Column(String, nullable=True)


class ServicePackage(Base):
    """Visits of one service a shop sells together, paid upfront: e.g. 5 haircuts for the price of 4."""

    __tablename__ = "service_packages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    shop_id = Column(String, nullable=False, index=True)
    service_id = Column(String, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    visits = Column(Integer, nullable=False)
    price_cents = Column(Integer, nullable=False)
    valid_days = Column(Integer, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)


class PackagePurchase(Base):
    """A customer's package: PENDING until paid, then ACTIVE with visits to book until it expires;
    REFUNDED once an admin refunds what is unused. Its terms are copied at purchase."""

    __tablename__ = "package_purchases"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    package_id = Column(String, ForeignKey("service_packages.id"), nullable=False, index=True)
    customer_id = Column(String, nullable=False, index=True)
    shop_id = Column(String, nullable=False, index=True)
    service_id = Column(String, nullable=False)
    name = Column(String(100), nullable=False)
    visits_total = Column(Integer, nullable=False)
    visits_left = Column(Integer, nullable=False)
    price_cents = Column(Integer, nullable=False)
    valid_days = Column(Integer, nullable=False)
    status = Column(String(10), nullable=False, default="PENDING")  # PENDING, ACTIVE, REFUNDED
    payment_id = Column(String, nullable=True)
    purchased_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)


class PackageRedemption(Base):
    """One visit of a package used for a booking (RETURNED if the booking was cancelled). The visit's share
    of the package price is what the shop earns when the booking is completed."""

    __tablename__ = "package_redemptions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    purchase_id = Column(String, ForeignKey("package_purchases.id"), nullable=False, index=True)
    booking_id = Column(String, nullable=False, unique=True)
    visit_value_cents = Column(Integer, nullable=False)
    status = Column(String(10), nullable=False, default="USED")  # USED, RETURNED
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
