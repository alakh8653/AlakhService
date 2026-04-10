import uuid
from datetime import datetime, timezone
from typing import Optional
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.payment import Account, Escrow, Payment
from app.core.ledger import ledger
from app.config import settings

log = structlog.get_logger()

VALID_ESCROW_TRANSITIONS = {
    "CREATED": {"HELD"},
    "HELD": {"RELEASED", "REFUNDED"},
}


class EscrowService:

    def _can_transition(self, from_state: str, to_state: str) -> bool:
        return to_state in VALID_ESCROW_TRANSITIONS.get(from_state, set())

    async def create_escrow(
        self,
        db: AsyncSession,
        payment_id: str,
        booking_id: str,
        amount_cents: int,
        currency: str = "INR",
    ) -> Escrow:
        now = datetime.now(timezone.utc)
        escrow = Escrow(
            id=str(uuid.uuid4()),
            payment_id=payment_id,
            booking_id=booking_id,
            amount_cents=amount_cents,
            currency=currency,
            status="CREATED",
            held_at=now,
        )
        db.add(escrow)
        await db.flush()
        log.info("escrow_created", escrow_id=escrow.id, payment_id=payment_id)
        return escrow

    async def hold_funds(self, db: AsyncSession, payment_id: str) -> Escrow:
        result = await db.execute(select(Escrow).where(Escrow.payment_id == payment_id))
        escrow = result.scalar_one_or_none()
        if not escrow:
            raise ValueError(f"Escrow not found for payment {payment_id}")

        if not self._can_transition(escrow.status, "HELD"):
            raise ValueError(f"Cannot transition escrow from {escrow.status} to HELD")

        escrow.status = "HELD"
        escrow.held_at = datetime.now(timezone.utc)
        await db.flush()

        log.info("escrow_held", escrow_id=escrow.id, amount_cents=escrow.amount_cents)
        return escrow

    async def _get_platform_account_id(self, db: AsyncSession) -> str:
        """Resolve the platform account row id by owner_id."""
        result = await db.execute(
            select(Account).where(Account.owner_id == settings.PLATFORM_ACCOUNT_ID)
        )
        account = result.scalar_one_or_none()
        if not account:
            raise ValueError(f"Platform account '{settings.PLATFORM_ACCOUNT_ID}' not found")
        return account.id

    async def release_funds(self, db: AsyncSession, payment_id: str, provider_account_id: str) -> Escrow:
        result = await db.execute(select(Escrow).where(Escrow.payment_id == payment_id))
        escrow = result.scalar_one_or_none()
        if not escrow:
            raise ValueError(f"Escrow not found for payment {payment_id}")

        if not self._can_transition(escrow.status, "RELEASED"):
            raise ValueError(f"Cannot transition escrow from {escrow.status} to RELEASED")

        result = await db.execute(select(Payment).where(Payment.id == payment_id))
        payment = result.scalar_one_or_none()
        if not payment:
            raise ValueError(f"Payment {payment_id} not found")

        platform_account_id = await self._get_platform_account_id(db)

        await ledger.transfer(
            db,
            from_account_id=platform_account_id,
            to_account_id=provider_account_id,
            amount_cents=escrow.amount_cents,
            currency=escrow.currency,
            description=f"Escrow release for booking {escrow.booking_id}",
            reference_id=escrow.id,
            reference_type="escrow_release",
        )

        escrow.status = "RELEASED"
        escrow.released_at = datetime.now(timezone.utc)
        await db.flush()

        log.info("escrow_released", escrow_id=escrow.id, provider_account=provider_account_id)
        return escrow

    async def refund_funds(self, db: AsyncSession, payment_id: str, payer_account_id: str, reason: str = "Refund") -> Escrow:
        result = await db.execute(select(Escrow).where(Escrow.payment_id == payment_id))
        escrow = result.scalar_one_or_none()
        if not escrow:
            raise ValueError(f"Escrow not found for payment {payment_id}")

        if not self._can_transition(escrow.status, "REFUNDED"):
            raise ValueError(f"Cannot transition escrow from {escrow.status} to REFUNDED")

        platform_account_id = await self._get_platform_account_id(db)

        await ledger.transfer(
            db,
            from_account_id=platform_account_id,
            to_account_id=payer_account_id,
            amount_cents=escrow.amount_cents,
            currency=escrow.currency,
            description=f"Escrow refund: {reason}",
            reference_id=escrow.id,
            reference_type="escrow_refund",
        )

        escrow.status = "REFUNDED"
        await db.flush()

        log.info("escrow_refunded", escrow_id=escrow.id, reason=reason)
        return escrow


escrow_service = EscrowService()
