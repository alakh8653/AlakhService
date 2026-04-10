import pytest
import pytest_asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/3"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.database import Base
from app.models.payment import Account, LedgerEntry, Payment, Escrow, Refund
from app.core.ledger import DoubleEntryLedger
from app.core.escrow import EscrowService
from app.services.payment_service import PaymentService
from app.schemas.payment import PaymentInitiate, RefundRequest

pytest_plugins = ("anyio",)

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine):
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
def mock_redis():
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock(return_value=True)
    return redis


@pytest_asyncio.fixture
def ledger_svc():
    return DoubleEntryLedger()


@pytest_asyncio.fixture
def escrow_svc():
    return EscrowService()


@pytest_asyncio.fixture
def payment_svc():
    return PaymentService()


async def create_account(db: AsyncSession, owner_id: str, balance_cents: int = 0, owner_type: str = "user") -> Account:
    now = datetime.now(timezone.utc)
    account = Account(
        id=str(uuid.uuid4()),
        owner_id=owner_id,
        owner_type=owner_type,
        balance_cents=balance_cents,
        currency="INR",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(account)
    await db.flush()
    return account


@pytest.mark.anyio
async def test_create_account(db_session, payment_svc):
    account = await payment_svc.get_or_create_account(db_session, "owner-1")
    assert account.owner_id == "owner-1"
    assert account.balance_cents == 0
    assert account.is_active is True


@pytest.mark.anyio
async def test_ledger_credit(db_session, ledger_svc):
    account = await create_account(db_session, "owner-2", balance_cents=0)
    entry = await ledger_svc.credit(
        db_session, account.id, 10000, "INR", "Initial deposit", "ref-1", "deposit"
    )
    assert entry.entry_type == "CREDIT"
    assert entry.amount_cents == 10000
    assert entry.running_balance == 10000

    balance = await ledger_svc.get_balance(db_session, account.id)
    assert balance == 10000


@pytest.mark.anyio
async def test_ledger_transfer(db_session, ledger_svc):
    acc_a = await create_account(db_session, "owner-a", balance_cents=50000)
    acc_b = await create_account(db_session, "owner-b", balance_cents=0)

    debit, credit = await ledger_svc.transfer(
        db_session, acc_a.id, acc_b.id, 20000, "INR", "Test transfer", "ref-2", "transfer"
    )
    assert debit.entry_type == "DEBIT"
    assert credit.entry_type == "CREDIT"
    assert debit.amount_cents == 20000
    assert credit.amount_cents == 20000

    bal_a = await ledger_svc.get_balance(db_session, acc_a.id)
    bal_b = await ledger_svc.get_balance(db_session, acc_b.id)
    assert bal_a == 30000
    assert bal_b == 20000


@pytest.mark.anyio
async def test_ledger_transfer_insufficient_funds(db_session, ledger_svc):
    acc_a = await create_account(db_session, "owner-c", balance_cents=1000)
    acc_b = await create_account(db_session, "owner-d", balance_cents=0)

    with pytest.raises(ValueError, match="Insufficient balance"):
        await ledger_svc.transfer(
            db_session, acc_a.id, acc_b.id, 5000, "INR", "Too much", "ref-3", "transfer"
        )


@pytest.mark.anyio
async def test_ledger_transfer_maintains_double_entry(db_session, ledger_svc):
    acc_a = await create_account(db_session, "owner-e", balance_cents=100000)
    acc_b = await create_account(db_session, "owner-f", balance_cents=0)

    debit, credit = await ledger_svc.transfer(
        db_session, acc_a.id, acc_b.id, 35000, "INR", "Double entry check", "ref-4", "transfer"
    )
    assert debit.amount_cents == credit.amount_cents


@pytest.mark.anyio
async def test_escrow_lifecycle_hold_release(db_session, escrow_svc, ledger_svc):
    # Create a platform account with enough funds
    platform_acc = await create_account(db_session, "platform_account", balance_cents=100000, owner_type="platform")
    provider_acc = await create_account(db_session, "provider-1", balance_cents=0, owner_type="provider")

    # Create a payment first (escrow needs a valid payment_id FK)
    now = datetime.now(timezone.utc)
    payment = Payment(
        id=str(uuid.uuid4()),
        booking_id="booking-1",
        payer_id="payer-1",
        payee_id="payee-1",
        amount_cents=5000,
        currency="INR",
        status="PENDING",
        payment_method="card",
        idempotency_key=str(uuid.uuid4()),
        created_at=now,
        updated_at=now,
    )
    db_session.add(payment)
    await db_session.flush()

    escrow = await escrow_svc.create_escrow(db_session, payment.id, "booking-1", 5000)
    assert escrow.status == "CREATED"

    held = await escrow_svc.hold_funds(db_session, payment.id)
    assert held.status == "HELD"

    released = await escrow_svc.release_funds(db_session, payment.id, provider_acc.id)
    assert released.status == "RELEASED"
    assert released.released_at is not None

    provider_balance = await ledger_svc.get_balance(db_session, provider_acc.id)
    assert provider_balance == 5000


@pytest.mark.anyio
async def test_escrow_invalid_transition_held_to_held(db_session, escrow_svc):
    now = datetime.now(timezone.utc)
    payment = Payment(
        id=str(uuid.uuid4()),
        booking_id="booking-2",
        payer_id="payer-2",
        payee_id="payee-2",
        amount_cents=3000,
        currency="INR",
        status="PENDING",
        payment_method="upi",
        idempotency_key=str(uuid.uuid4()),
        created_at=now,
        updated_at=now,
    )
    db_session.add(payment)
    await db_session.flush()

    await escrow_svc.create_escrow(db_session, payment.id, "booking-2", 3000)
    await escrow_svc.hold_funds(db_session, payment.id)

    with pytest.raises(ValueError, match="Cannot transition escrow from HELD to HELD"):
        await escrow_svc.hold_funds(db_session, payment.id)


@pytest.mark.anyio
async def test_escrow_held_to_refunded(db_session, escrow_svc, ledger_svc):
    platform_acc = await create_account(db_session, "platform_account", balance_cents=50000, owner_type="platform")
    payer_acc = await create_account(db_session, "payer-r", balance_cents=0, owner_type="user")

    now = datetime.now(timezone.utc)
    payment = Payment(
        id=str(uuid.uuid4()),
        booking_id="booking-3",
        payer_id="payer-r",
        payee_id="payee-r",
        amount_cents=8000,
        currency="INR",
        status="PENDING",
        payment_method="card",
        idempotency_key=str(uuid.uuid4()),
        created_at=now,
        updated_at=now,
    )
    db_session.add(payment)
    await db_session.flush()

    await escrow_svc.create_escrow(db_session, payment.id, "booking-3", 8000)
    await escrow_svc.hold_funds(db_session, payment.id)
    refunded = await escrow_svc.refund_funds(db_session, payment.id, payer_acc.id, "Cancelled")
    assert refunded.status == "REFUNDED"

    payer_balance = await ledger_svc.get_balance(db_session, payer_acc.id)
    assert payer_balance == 8000


@pytest.mark.anyio
async def test_initiate_payment_creates_escrow(db_session, payment_svc, mock_redis):
    from sqlalchemy import select as sa_select
    payment_data = PaymentInitiate(
        booking_id="booking-init-1",
        payer_id="payer-init-1",
        payee_id="payee-init-1",
        amount_cents=12000,
        currency="INR",
        payment_method="card",
        idempotency_key=str(uuid.uuid4()),
    )
    payment = await payment_svc.initiate_payment(db_session, mock_redis, payment_data)
    assert payment.status == "PENDING"

    result = await db_session.execute(sa_select(Escrow).where(Escrow.payment_id == payment.id))
    escrow = result.scalar_one_or_none()
    assert escrow is not None
    assert escrow.amount_cents == 12000
    assert escrow.status == "CREATED"


@pytest.mark.anyio
async def test_idempotency(db_session, payment_svc, mock_redis):
    idem_key = str(uuid.uuid4())
    payment_data = PaymentInitiate(
        booking_id="booking-idem-1",
        payer_id="payer-idem-1",
        payee_id="payee-idem-1",
        amount_cents=9000,
        currency="INR",
        payment_method="upi",
        idempotency_key=idem_key,
    )

    payment1 = await payment_svc.initiate_payment(db_session, mock_redis, payment_data)

    # Second call with same key (Redis returns None but DB has the record)
    payment2 = await payment_svc.initiate_payment(db_session, mock_redis, payment_data)
    assert payment1.id == payment2.id
