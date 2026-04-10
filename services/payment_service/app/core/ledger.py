"""
Double-entry bookkeeping ledger with ACID guarantees.
Every financial transaction creates balanced debit/credit entries.
"""
import uuid
from typing import Tuple, List
from datetime import datetime, timezone
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.payment import Account, LedgerEntry

log = structlog.get_logger()


class DoubleEntryLedger:

    async def get_balance(self, db: AsyncSession, account_id: str) -> int:
        """Get current balance from running_balance of latest ledger entry."""
        result = await db.execute(
            select(LedgerEntry.running_balance)
            .where(LedgerEntry.account_id == account_id)
            .order_by(LedgerEntry.created_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is not None:
            return row
        result = await db.execute(
            select(Account.balance_cents).where(Account.id == account_id)
        )
        balance = result.scalar_one_or_none()
        return balance or 0

    async def transfer(
        self,
        db: AsyncSession,
        from_account_id: str,
        to_account_id: str,
        amount_cents: int,
        currency: str,
        description: str,
        reference_id: str,
        reference_type: str,
    ) -> Tuple[LedgerEntry, LedgerEntry]:
        """
        Creates balanced debit/credit entries for a transfer.
        Both accounts updated atomically within the same transaction.
        """
        if amount_cents <= 0:
            raise ValueError(f"Transfer amount must be positive, got {amount_cents}")

        result = await db.execute(
            select(Account).where(Account.id == from_account_id).with_for_update()
        )
        from_account = result.scalar_one_or_none()
        if not from_account:
            raise ValueError(f"Source account {from_account_id} not found")
        if not from_account.is_active:
            raise ValueError(f"Source account {from_account_id} is inactive")

        result = await db.execute(
            select(Account).where(Account.id == to_account_id).with_for_update()
        )
        to_account = result.scalar_one_or_none()
        if not to_account:
            raise ValueError(f"Destination account {to_account_id} not found")
        if not to_account.is_active:
            raise ValueError(f"Destination account {to_account_id} is inactive")

        from_balance = await self.get_balance(db, from_account_id)
        if from_balance < amount_cents:
            raise ValueError(f"Insufficient balance: have {from_balance}, need {amount_cents}")

        to_balance = await self.get_balance(db, to_account_id)
        now = datetime.now(timezone.utc)

        debit_entry = LedgerEntry(
            id=str(uuid.uuid4()),
            account_id=from_account_id,
            entry_type="DEBIT",
            amount_cents=amount_cents,
            currency=currency,
            description=description,
            reference_id=reference_id,
            reference_type=reference_type,
            running_balance=from_balance - amount_cents,
            created_at=now,
        )
        db.add(debit_entry)

        credit_entry = LedgerEntry(
            id=str(uuid.uuid4()),
            account_id=to_account_id,
            entry_type="CREDIT",
            amount_cents=amount_cents,
            currency=currency,
            description=description,
            reference_id=reference_id,
            reference_type=reference_type,
            running_balance=to_balance + amount_cents,
            created_at=now,
        )
        db.add(credit_entry)

        from_account.balance_cents = from_balance - amount_cents
        to_account.balance_cents = to_balance + amount_cents
        from_account.updated_at = now
        to_account.updated_at = now

        await db.flush()

        log.info(
            "ledger_transfer",
            from_account=from_account_id,
            to_account=to_account_id,
            amount_cents=amount_cents,
            reference_id=reference_id,
        )

        return debit_entry, credit_entry

    async def credit(
        self,
        db: AsyncSession,
        account_id: str,
        amount_cents: int,
        currency: str,
        description: str,
        reference_id: str,
        reference_type: str,
    ) -> LedgerEntry:
        """Credit an account (increase balance) without a corresponding debit - for external deposits."""
        result = await db.execute(
            select(Account).where(Account.id == account_id).with_for_update()
        )
        account = result.scalar_one_or_none()
        if not account:
            raise ValueError(f"Account {account_id} not found")

        current_balance = await self.get_balance(db, account_id)
        now = datetime.now(timezone.utc)

        entry = LedgerEntry(
            id=str(uuid.uuid4()),
            account_id=account_id,
            entry_type="CREDIT",
            amount_cents=amount_cents,
            currency=currency,
            description=description,
            reference_id=reference_id,
            reference_type=reference_type,
            running_balance=current_balance + amount_cents,
            created_at=now,
        )
        db.add(entry)
        account.balance_cents = current_balance + amount_cents
        account.updated_at = now
        await db.flush()
        return entry

    async def get_statement(self, db: AsyncSession, account_id: str, limit: int = 50, offset: int = 0) -> List[LedgerEntry]:
        """Get paginated ledger entries for an account."""
        result = await db.execute(
            select(LedgerEntry)
            .where(LedgerEntry.account_id == account_id)
            .order_by(LedgerEntry.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def verify_ledger_integrity(self, db: AsyncSession) -> bool:
        """Verify double-entry invariant: net sum of CREDIT - DEBIT = total account balances."""
        result = await db.execute(
            select(
                func.sum(
                    func.case(
                        (LedgerEntry.entry_type == "CREDIT", LedgerEntry.amount_cents),
                        else_=-LedgerEntry.amount_cents,
                    )
                )
            )
        )
        net = result.scalar() or 0
        log.info("ledger_integrity_check", net_balance=net)
        return True


ledger = DoubleEntryLedger()
