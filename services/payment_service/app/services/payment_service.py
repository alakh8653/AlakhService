import uuid
import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Optional
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import redis.asyncio as aioredis

from app.models.payment import Payment, Account, Refund, Escrow, LedgerEntry
from app.schemas.payment import PaymentInitiate, RefundRequest
from app.core.ledger import ledger
from app.core.escrow import escrow_service
from app.config import settings

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
        result = await db.execute(
            select(Payment).where(Payment.idempotency_key == payment_data.idempotency_key)
        )
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
            db, payment.id, payment_data.booking_id,
            payment_data.amount_cents, payment_data.currency,
        )

        await redis.setex(idempotency_key, 86400, payment.id)

        log.info("payment_initiated", payment_id=payment.id, amount_cents=payment_data.amount_cents)
        return payment

    async def process_razorpay_webhook(self, db: AsyncSession, payload: dict, signature: str) -> bool:
        if settings.RAZORPAY_KEY_SECRET:
            webhook_body = json.dumps(payload, separators=(",", ":")).encode()
            expected = hmac.new(
                settings.RAZORPAY_KEY_SECRET.encode(),
                webhook_body,
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(expected, signature):
                raise ValueError("Invalid Razorpay signature")

        event = payload.get("event", "")
        entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        provider_payment_id = entity.get("id")

        if event == "payment.captured":
            notes = entity.get("notes", {})
            internal_payment_id = notes.get("payment_id")
            if internal_payment_id:
                result = await db.execute(select(Payment).where(Payment.id == internal_payment_id))
                payment = result.scalar_one_or_none()
                if payment:
                    payment.status = "COMPLETED"
                    payment.provider_payment_id = provider_payment_id
                    payment.gateway = "razorpay"
                    payment.updated_at = datetime.now(timezone.utc)
                    try:
                        await escrow_service.hold_funds(db, payment.id)
                        platform_account = await self.get_or_create_account(
                            db, settings.PLATFORM_ACCOUNT_ID, "platform"
                        )
                        await ledger.credit(
                            db, platform_account.id, payment.amount_cents,
                            payment.currency, f"Payment {payment.id} received",
                            payment.id, "payment",
                        )
                    except Exception as e:
                        log.warning("escrow_hold_failed", error=str(e))
                    await db.flush()
                    log.info("razorpay_payment_captured", payment_id=payment.id)

        elif event == "payment.failed":
            notes = entity.get("notes", {})
            internal_payment_id = notes.get("payment_id")
            if internal_payment_id:
                result = await db.execute(select(Payment).where(Payment.id == internal_payment_id))
                payment = result.scalar_one_or_none()
                if payment:
                    payment.status = "FAILED"
                    payment.updated_at = datetime.now(timezone.utc)
                    await db.flush()

        return True

    async def process_stripe_webhook(self, db: AsyncSession, payload: bytes, signature: str) -> bool:
        if settings.STRIPE_WEBHOOK_SECRET:
            import stripe
            try:
                event = stripe.Webhook.construct_event(payload, signature, settings.STRIPE_WEBHOOK_SECRET)
            except Exception as e:
                raise ValueError(f"Invalid Stripe signature: {e}")
            event_type = event["type"]
            event_data = event["data"]["object"]
        else:
            event_data = payload if isinstance(payload, dict) else {}
            event_type = event_data.get("type", "")

        if event_type == "payment_intent.succeeded":
            internal_payment_id = event_data.get("metadata", {}).get("payment_id")
            if internal_payment_id:
                result = await db.execute(select(Payment).where(Payment.id == internal_payment_id))
                payment = result.scalar_one_or_none()
                if payment:
                    payment.status = "COMPLETED"
                    payment.provider_payment_id = event_data.get("id")
                    payment.gateway = "stripe"
                    payment.updated_at = datetime.now(timezone.utc)
                    await db.flush()
                    log.info("stripe_payment_succeeded", payment_id=payment.id)

        return True

    async def request_refund(self, db: AsyncSession, payment_id: str, refund_data: RefundRequest) -> Refund:
        result = await db.execute(select(Payment).where(Payment.id == payment_id))
        payment = result.scalar_one_or_none()
        if not payment:
            raise ValueError(f"Payment {payment_id} not found")

        if payment.status not in ("COMPLETED",):
            raise ValueError(f"Cannot refund payment with status {payment.status}")

        if refund_data.amount_cents > payment.amount_cents:
            raise ValueError("Refund amount exceeds payment amount")

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

        payment.status = "REFUNDED" if refund_data.amount_cents == payment.amount_cents else "PARTIALLY_REFUNDED"
        payment.updated_at = now
        await db.flush()

        log.info("refund_requested", payment_id=payment_id, amount=refund_data.amount_cents)
        return refund

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

        count_result = await db.execute(
            select(func.count()).where(LedgerEntry.account_id == account_id)
        )
        total = count_result.scalar() or 0

        return {"items": entries, "total": total, "page": page, "per_page": per_page}


payment_service = PaymentService()
