import uuid
from datetime import datetime, timezone
from typing import List, Optional

import redis.asyncio as aioredis
import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.escrow import escrow_service
from app.core.ledger import ledger
from app.models.payment import Account, LedgerEntry, Payment, Refund
from app.schemas.payment import PaymentInitiate, RefundRequest

log = structlog.get_logger()


class PaymentService:
    async def get_or_create_account(
        self,
        db: AsyncSession,
        owner_id: str,
        owner_type: str = "user",
        currency: str = "INR",
    ) -> Account:
        result = await db.execute(select(Account).where(Account.owner_id == owner_id))
        account = result.scalar_one_or_none()
        if not account:
            now = datetime.now(timezone.utc)
            account = Account(
                id=str(uuid.uuid4()),
                owner_id=owner_id,
                owner_type=owner_type,
                balance_cents=0,
                currency=currency,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            db.add(account)
            await db.flush()
        return account

    async def initiate_payment(
        self,
        db: AsyncSession,
        redis: aioredis.Redis,
        payment_data: PaymentInitiate,
    ) -> Payment:
        # Idempotency check via Redis cache
        idempotency_key = f"payment:idempotency:{payment_data.idempotency_key}"
        cached = await redis.get(idempotency_key)
        if cached:
            payment_id = cached.decode() if isinstance(cached, bytes) else cached
            result = await db.execute(select(Payment).where(Payment.id == payment_id))
            existing = result.scalar_one_or_none()
            if existing:
                log.info("payment_idempotent_return", payment_id=payment_id)
                return existing

        # Idempotency check via DB
        result = await db.execute(select(Payment).where(Payment.idempotency_key == payment_data.idempotency_key))
        existing = result.scalar_one_or_none()
        if existing:
            return existing

        now = datetime.now(timezone.utc)
        payment = Payment(
            id=str(uuid.uuid4()),
            booking_id=payment_data.booking_id,
            payer_id=payment_data.payer_id,
            payee_id=payment_data.payee_id,
            amount_cents=payment_data.amount_cents,
            currency=payment_data.currency,
            status="PENDING",
            payment_method=payment_data.payment_method,
            idempotency_key=payment_data.idempotency_key,
            created_at=now,
            updated_at=now,
        )
        db.add(payment)
        await db.flush()

        await escrow_service.create_escrow(
            db,
            payment.id,
            payment_data.booking_id,
            payment_data.amount_cents,
            payment_data.currency,
        )

        await redis.setex(idempotency_key, 86400, payment.id)

        log.info("payment_initiated", payment_id=payment.id, amount_cents=payment_data.amount_cents)
        return payment

    async def mark_completed(
        self, db: AsyncSession, payment: Payment, provider_payment_id: str, gateway: str
    ) -> Payment:
        """Records a confirmed payment once: funds go into escrow and the platform account is credited."""
        if payment.status == "COMPLETED":
            return payment
        payment.status = "COMPLETED"
        payment.provider_payment_id = provider_payment_id
        payment.gateway = gateway
        payment.updated_at = datetime.now(timezone.utc)
        try:
            await escrow_service.hold_funds(db, payment.id)
            platform_account = await self.get_or_create_account(db, settings.PLATFORM_ACCOUNT_ID, "platform")
            await ledger.credit(
                db,
                platform_account.id,
                payment.amount_cents,
                payment.currency,
                f"Payment {payment.id} received",
                payment.id,
                "payment",
            )
        except Exception as e:
            log.warning("escrow_hold_failed", payment_id=payment.id, error=str(e))
        # Other attempts at paying this booking (e.g. a cash choice, then UPI) are now moot.
        others = await db.execute(
            select(Payment).where(
                Payment.booking_id == payment.booking_id, Payment.id != payment.id, Payment.status == "PENDING"
            )
        )
        for other in others.scalars().all():
            other.status = "CANCELLED"
            other.updated_at = payment.updated_at
        await db.flush()
        log.info("payment_completed", payment_id=payment.id, gateway=gateway)
        return payment

    async def _find_for_gateway(
        self, db: AsyncSession, payment_id: Optional[str], order_id: Optional[str]
    ) -> Optional[Payment]:
        if payment_id:
            payment = await self.get_payment(db, payment_id)
            if payment:
                return payment
        if order_id:
            result = await db.execute(select(Payment).where(Payment.provider_order_id == order_id))
            return result.scalar_one_or_none()
        return None

    async def process_razorpay_event(self, db: AsyncSession, event: dict) -> Optional[tuple[str, Payment]]:
        """Applies a Razorpay webhook event whose signature has already been checked.

        Returns what changed (``("payment.completed", payment)`` or ``("payment.failed", payment)``), if anything.
        """
        entity = event.get("payload", {}).get("payment", {}).get("entity", {})
        payment = await self._find_for_gateway(
            db, (entity.get("notes") or {}).get("payment_id"), entity.get("order_id")
        )
        if payment is None:
            log.info("razorpay_event_unmatched", event=event.get("event"), order_id=entity.get("order_id"))
            return None
        if event.get("event") in ("payment.captured", "order.paid"):
            if (
                entity.get("amount") != payment.amount_cents
                or entity.get("currency", payment.currency) != payment.currency
            ):
                log.warning("razorpay_amount_mismatch", payment_id=payment.id, amount=entity.get("amount"))
                return None
            if payment.status == "COMPLETED":
                return None
            await self.mark_completed(db, payment, entity.get("id"), "razorpay")
            return "payment.completed", payment
        if event.get("event") == "payment.failed" and payment.status == "PENDING":
            payment.status = "FAILED"
            payment.updated_at = datetime.now(timezone.utc)
            await db.flush()
            return "payment.failed", payment
        return None

    async def process_stripe_event(self, db: AsyncSession, event: dict) -> None:
        """Applies a Stripe webhook event whose signature has already been checked."""
        if event.get("type") != "payment_intent.succeeded":
            return
        intent = event.get("data", {}).get("object", {})
        payment = await self._find_for_gateway(db, (intent.get("metadata") or {}).get("payment_id"), None)
        if payment and intent.get("amount_received", intent.get("amount")) == payment.amount_cents:
            await self.mark_completed(db, payment, intent.get("id"), "stripe")

    async def request_refund(
        self, db: AsyncSession, payment_id: str, refund_data: RefundRequest, gateway=None
    ) -> Refund:
        """Refunds part or all of a payment that is still unrefunded.

        Card/UPI payments are refunded through Razorpay (the request fails if Razorpay refuses);
        cash payments are recorded as MANUAL refunds, settled in person.
        """
        payment = await self.get_payment(db, payment_id)
        if not payment:
            raise ValueError(f"Payment {payment_id} not found")
        if payment.status not in ("COMPLETED", "PARTIALLY_REFUNDED"):
            raise ValueError(f"Cannot refund payment with status {payment.status}")

        already = await self._refunded_cents(db, payment.id)
        if already + refund_data.amount_cents > payment.amount_cents:
            raise ValueError(f"Refund exceeds what is left to refund ({payment.amount_cents - already} paise)")

        now = datetime.now(timezone.utc)
        refund = Refund(
            id=str(uuid.uuid4()),
            payment_id=payment_id,
            amount_cents=refund_data.amount_cents,
            reason=refund_data.reason,
            status="PENDING",
            created_at=now,
        )
        db.add(refund)

        if payment.gateway == "razorpay" and payment.provider_payment_id:
            if gateway is None or not gateway.configured:
                raise ValueError("Razorpay is not configured, so this payment cannot be refunded")
            result = await gateway.refund(
                payment.provider_payment_id,
                refund_data.amount_cents,
                {"refund_id": refund.id, "reason": refund_data.reason[:200]},
            )
            refund.gateway_refund_id = result.get("id")
            refund.status = "PROCESSED" if result.get("status") == "processed" else "PENDING"
        else:
            refund.status = "MANUAL"

        refunded_in_full = already + refund_data.amount_cents == payment.amount_cents
        payment.status = "REFUNDED" if refunded_in_full else "PARTIALLY_REFUNDED"
        payment.updated_at = now
        await db.flush()
        await self._return_funds(db, payment, refund_data.amount_cents, refunded_in_full, refund_data.reason)

        log.info("refund_issued", payment_id=payment_id, amount=refund_data.amount_cents, status=refund.status)
        return refund

    async def _refunded_cents(self, db: AsyncSession, payment_id: str) -> int:
        result = await db.execute(
            select(func.coalesce(func.sum(Refund.amount_cents), 0)).where(
                Refund.payment_id == payment_id, Refund.status != "FAILED"
            )
        )
        return int(result.scalar() or 0)

    async def _return_funds(
        self, db: AsyncSession, payment: Payment, amount_cents: int, in_full: bool, reason: str
    ) -> None:
        """Moves the refunded amount from the platform back to the payer in the ledger."""
        try:
            payer = await self.get_or_create_account(db, payment.payer_id, "user", payment.currency)
            if in_full and amount_cents == payment.amount_cents:
                await escrow_service.refund_funds(db, payment.id, payer.id, reason)
            else:
                platform = await self.get_or_create_account(db, settings.PLATFORM_ACCOUNT_ID, "platform")
                await ledger.transfer(
                    db,
                    from_account_id=platform.id,
                    to_account_id=payer.id,
                    amount_cents=amount_cents,
                    currency=payment.currency,
                    description=f"Refund: {reason}",
                    reference_id=payment.id,
                    reference_type="refund",
                )
        except Exception as e:  # the refund itself stands; the books are reconciled by finance
            log.warning("refund_ledger_failed", payment_id=payment.id, error=str(e))

    async def process_refund_event(self, db: AsyncSession, event: dict) -> Optional[Refund]:
        """refund.processed / refund.failed from Razorpay; returns the refund if its status changed."""
        entity = event.get("payload", {}).get("refund", {}).get("entity", {})
        if not entity.get("id"):
            return None
        refund = (await db.execute(select(Refund).where(Refund.gateway_refund_id == entity["id"]))).scalar_one_or_none()
        if refund is None:
            return None
        if event.get("event") == "refund.processed" and refund.status != "PROCESSED":
            refund.status = "PROCESSED"
        elif event.get("event") == "refund.failed" and refund.status != "FAILED":
            refund.status = "FAILED"
            # The money never left: the payment is back to what the other refunds leave it at.
            payment = await self.get_payment(db, refund.payment_id)
            await db.flush()
            remaining = await self._refunded_cents(db, refund.payment_id)
            if payment:
                payment.status = (
                    "COMPLETED"
                    if remaining == 0
                    else ("REFUNDED" if remaining == payment.amount_cents else "PARTIALLY_REFUNDED")
                )
        else:
            return None
        await db.flush()
        return refund

    async def payments_by_payer(self, db: AsyncSession, payer_id: str, limit: int = 100) -> List[Payment]:
        result = await db.execute(
            select(Payment).where(Payment.payer_id == payer_id).order_by(Payment.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def payments_for_booking(self, db: AsyncSession, booking_id: str) -> List[Payment]:
        result = await db.execute(select(Payment).where(Payment.booking_id == booking_id).order_by(Payment.created_at))
        return list(result.scalars().all())

    async def get_payment(self, db: AsyncSession, payment_id: str) -> Optional[Payment]:
        result = await db.execute(select(Payment).where(Payment.id == payment_id))
        return result.scalar_one_or_none()

    async def get_account_balance(self, db: AsyncSession, account_id: str) -> int:
        return await ledger.get_balance(db, account_id)

    async def get_transaction_history(
        self,
        db: AsyncSession,
        account_id: str,
        page: int = 1,
        per_page: int = 20,
    ) -> dict:
        offset = (page - 1) * per_page
        entries = await ledger.get_statement(db, account_id, limit=per_page, offset=offset)

        count_result = await db.execute(select(func.count()).where(LedgerEntry.account_id == account_id))
        total = count_result.scalar() or 0

        return {"items": entries, "total": total, "page": page, "per_page": per_page}


payment_service = PaymentService()
