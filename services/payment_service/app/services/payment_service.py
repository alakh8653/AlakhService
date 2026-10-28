import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

import redis.asyncio as aioredis
import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core import money
from app.core.escrow import escrow_service
from app.core.ledger import ledger
from app.core.razorpay import GatewayError
from app.models.payment import BOOKING, PACKAGE, TIP, Account, LedgerEntry, Payment, Refund
from app.schemas.payment import PaymentInitiate, RefundRequest
from app.services import earnings_service, invoice_service, loyalty_service, package_service

log = structlog.get_logger()

# Payments that mean the booking is settled (refunds included: the customer already paid once).
PAID_STATUSES = {"COMPLETED", "PARTIALLY_REFUNDED", "REFUNDED"}
# Never settled on our books, so a capture the gateway reports for one is new money, not a replay.
UNSETTLED_STATUSES = {"PENDING", "CANCELLED", "FAILED"}
DUPLICATE_REFUND_REASON = "Booking was already paid for"
CANCELLED_REFUND_REASON = "Booking was cancelled"


class PaymentService:
    async def get_or_create_account(
        self,
        db: AsyncSession,
        owner_id: str,
        owner_type: str = "user",
        currency: str = "INR",
    ) -> Account:
        account = await self.account_for_owner(db, owner_id)
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

    async def account_for_owner(self, db: AsyncSession, owner_id: str) -> Optional[Account]:
        result = await db.execute(select(Account).where(Account.owner_id == owner_id))
        return result.scalar_one_or_none()

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
            shop_id=payment_data.shop_id,
            amount_cents=payment_data.amount_cents,
            currency=payment_data.currency,
            status="PENDING",
            payment_method=payment_data.payment_method,
            idempotency_key=payment_data.idempotency_key,
            purpose=payment_data.purpose,
            metadata_json=payment_data.metadata_json,
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
        """Records a confirmed payment once and gives it its invoice number.

        Money collected online goes into escrow on the platform account. Cash went straight to the shop,
        so it never touches escrow or the platform's books; the commission it owes is recorded when the
        booking completes.

        Only a pending payment completes; one already settled (or refunded, failed, cancelled) stays as it is.
        """
        if payment.status != "PENDING":
            return payment
        payment.status = "COMPLETED"
        payment.provider_payment_id = provider_payment_id
        payment.gateway = gateway
        payment.updated_at = datetime.now(timezone.utc)
        if gateway != "cash":
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
        # Other attempts at paying this booking (e.g. a cash choice, then UPI) are now moot; a tip's
        # checkout and the booking's own are separate.
        others = await db.execute(
            select(Payment).where(
                Payment.booking_id == payment.booking_id,
                Payment.purpose == payment.purpose,
                Payment.id != payment.id,
                Payment.status == "PENDING",
            )
        )
        for other in others.scalars().all():
            other.status = "CANCELLED"
            other.updated_at = payment.updated_at
        await db.flush()
        if payment.purpose == TIP:
            # Passed on in full to the provider: no service is sold, so there is no invoice.
            await earnings_service.tip_completed(db, payment)
        elif payment.purpose == PACKAGE:
            # Prepaid visits: invoiced now; the shop earns each visit's share as it is completed.
            await invoice_service.assign_invoice(db, payment)
            await package_service.payment_completed(db, payment)
        else:
            await invoice_service.assign_invoice(db, payment)
            await earnings_service.payment_completed(db, payment)
        log.info("payment_completed", payment_id=payment.id, gateway=gateway, invoice=payment.invoice_number)
        return payment

    async def record_capture(
        self, db: AsyncSession, payment: Payment, provider_payment_id: str, gateway_name: str, gateway=None
    ) -> Optional[str]:
        """The gateway says it captured money for [payment]; returns the event to announce, if anything changed.

        A replayed confirmation changes nothing. Money captured for a booking that is already paid for
        (a second checkout was paid too) is not kept: it is refunded through Razorpay, or marked DUPLICATE
        for an admin to refund when that is not possible.
        """
        # Lock the booking's payments (or tips) so two checkouts confirmed at once cannot both complete.
        result = await db.execute(
            select(Payment)
            .where(Payment.booking_id == payment.booking_id, Payment.purpose == payment.purpose)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        siblings = list(result.scalars().all())
        if payment.status not in UNSETTLED_STATUSES:
            return None
        if any(p.id != payment.id and p.status in PAID_STATUSES for p in siblings):
            payment.provider_payment_id = provider_payment_id
            payment.gateway = gateway_name
            payment.updated_at = datetime.now(timezone.utc)
            await self._refund_duplicate(db, payment, gateway)
            return "payment.refunded" if payment.status == "REFUNDED" else None
        if payment.status == "CANCELLED":
            # The booking was cancelled while this checkout was open: the money goes straight back.
            payment.provider_payment_id = provider_payment_id
            payment.gateway = gateway_name
            payment.updated_at = datetime.now(timezone.utc)
            await self._refund_duplicate(db, payment, gateway, CANCELLED_REFUND_REASON)
            return "payment.refunded" if payment.status == "REFUNDED" else None
        if payment.status != "PENDING":
            log.warning("capture_for_closed_payment", payment_id=payment.id, status=payment.status)
            return None
        await self.mark_completed(db, payment, provider_payment_id, gateway_name)
        return "payment.completed"

    async def _refund_duplicate(
        self, db: AsyncSession, payment: Payment, gateway, reason: str = DUPLICATE_REFUND_REASON
    ) -> None:
        """Gives a payment the booking cannot keep back in full (a second payment, or one for a booking
        already cancelled). It never reached escrow or the ledger."""
        if payment.gateway == "razorpay" and gateway is not None and gateway.configured:
            refund = Refund(
                id=str(uuid.uuid4()),
                payment_id=payment.id,
                amount_cents=payment.amount_cents,
                reason=reason,
                status="PENDING",
                created_at=payment.updated_at,
            )
            try:
                result = await gateway.refund(
                    payment.provider_payment_id,
                    payment.amount_cents,
                    {"refund_id": refund.id, "reason": reason},
                )
            except GatewayError as e:
                log.warning("duplicate_refund_failed", payment_id=payment.id, error=str(e))
            else:
                refund.gateway_refund_id = result.get("id")
                refund.status = "PROCESSED" if result.get("status") == "processed" else "PENDING"
                db.add(refund)
                payment.status = "REFUNDED"
                await db.flush()
                log.warning("duplicate_payment_refunded", payment_id=payment.id, booking_id=payment.booking_id)
                return
        payment.status = "DUPLICATE"
        await db.flush()
        log.warning("duplicate_payment_needs_refund", payment_id=payment.id, booking_id=payment.booking_id)

    async def _another_paid(self, db: AsyncSession, payment: Payment) -> bool:
        result = await db.execute(
            select(Payment.id).where(
                Payment.booking_id == payment.booking_id,
                Payment.purpose == payment.purpose,
                Payment.id != payment.id,
                Payment.status.in_(PAID_STATUSES),
            )
        )
        return result.first() is not None

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

    async def process_razorpay_event(
        self, db: AsyncSession, event: dict, gateway=None
    ) -> Optional[tuple[str, Payment]]:
        """Applies a Razorpay webhook event whose signature has already been checked.

        Returns what changed (e.g. ``("payment.completed", payment)`` or ``("payment.failed", payment)``), if anything.
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
            changed = await self.record_capture(db, payment, entity.get("id"), "razorpay", gateway)
            return (changed, payment) if changed else None
        if event.get("event") == "payment.failed" and payment.status == "PENDING":
            payment.status = "FAILED"
            payment.updated_at = datetime.now(timezone.utc)
            await db.flush()
            return "payment.failed", payment
        return None

    async def request_refund(
        self,
        db: AsyncSession,
        payment_id: str,
        refund_data: RefundRequest,
        gateway=None,
        idempotency_key: Optional[str] = None,
    ) -> Refund:
        """Refunds part or all of a payment that is still unrefunded.

        Card/UPI payments are refunded through Razorpay (the request fails if Razorpay refuses);
        cash payments are recorded as MANUAL refunds, settled in person. With [idempotency_key] a
        repeated request returns the refund already made instead of refunding again.
        """
        if idempotency_key:
            earlier = (
                await db.execute(select(Refund).where(Refund.idempotency_key == idempotency_key))
            ).scalar_one_or_none()
            if earlier is not None:
                return earlier
        payment = await self.get_payment(db, payment_id)
        if not payment:
            raise ValueError(f"Payment {payment_id} not found")
        if payment.status not in ("COMPLETED", "PARTIALLY_REFUNDED", "DUPLICATE"):
            raise ValueError(f"Cannot refund payment with status {payment.status}")
        duplicate = payment.status == "DUPLICATE"
        if duplicate and refund_data.amount_cents != payment.amount_cents:
            raise ValueError("A duplicate payment is refunded in full")

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
            idempotency_key=idempotency_key,
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
        if not duplicate:  # a duplicate never reached escrow or the ledger
            if payment.gateway != "cash":  # nor did cash, which the shop took
                await self._return_funds(db, payment, refund_data.amount_cents, refunded_in_full, refund_data.reason)
            await earnings_service.after_refund(db, payment)

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
            if payment and remaining == 0:
                # A duplicate whose refund failed still has to be refunded, not counted as the booking's payment.
                payment.status = "DUPLICATE" if await self._another_paid(db, payment) else "COMPLETED"
            elif payment:
                payment.status = "REFUNDED" if remaining == payment.amount_cents else "PARTIALLY_REFUNDED"
            if payment and payment.status != "DUPLICATE":
                await db.flush()
                await earnings_service.after_refund(db, payment)
        else:
            return None
        await db.flush()
        return refund

    async def booking_cancelled(
        self,
        db: AsyncSession,
        booking_id: str,
        cancelled_by: str,
        scheduled_at: Optional[datetime],
        cancelled_at: Optional[datetime],
        gateway=None,
    ) -> dict:
        """Refunds a cancelled booking's payment as the cancellation policy says (see app.core.money).

        Safe to call again (booking_service retries until it gets an answer): the refund carries the key
        cancel:{booking_id}, so it is made once. Checkouts still open are closed, and money captured for
        one later is refunded in full. Raises GatewayError when Razorpay cannot be reached, so the caller
        retries.
        """
        now = datetime.now(timezone.utc)
        # Points or a package visit spent on it go back, whatever happens to its money.
        await loyalty_service.return_points(db, booking_id)
        await package_service.return_visit(db, booking_id)
        payments = await self.payments_for_booking(db, booking_id)
        for p in payments:
            if p.status == "PENDING":
                p.status = "CANCELLED"
                p.updated_at = now
        await db.flush()
        paid = next((p for p in payments if p.status in ("COMPLETED", "PARTIALLY_REFUNDED")), None)
        key = f"cancel:{booking_id}"
        earlier = (await db.execute(select(Refund).where(Refund.idempotency_key == key))).scalar_one_or_none()
        if earlier is not None:
            payment = await self.get_payment(db, earlier.payment_id)
            return self._cancel_result(booking_id, payment, earlier, 0, "already_refunded")
        if paid is None:
            return self._cancel_result(booking_id, None, None, 0, "nothing_to_refund")
        refundable = paid.amount_cents - await self._refunded_cents(db, paid.id)
        policy = money.cancel_refund(
            refundable,
            cancelled_by,
            scheduled_at,
            cancelled_at or now,
            settings.CANCEL_FREE_HOURS,
            Decimal(settings.CANCEL_FEE_PERCENT),
        )
        refund = None
        if policy.refund_cents > 0:
            refund = await self.request_refund(
                db,
                paid.id,
                RefundRequest(amount_cents=policy.refund_cents, reason=f"Booking cancelled ({policy.rule})"),
                gateway,
                idempotency_key=key,
            )
        if policy.fee_cents > 0:
            # The late-cancellation fee is the shop's, less the platform's commission.
            await earnings_service.settle_booking(db, booking_id, paid.shop_id, None)
        log.info(
            "cancel_refund",
            booking_id=booking_id,
            cancelled_by=cancelled_by,
            refund_cents=policy.refund_cents,
            fee_cents=policy.fee_cents,
            rule=policy.rule,
        )
        return self._cancel_result(booking_id, paid, refund, policy.fee_cents, "refunded" if refund else "fee_kept")

    @staticmethod
    def _cancel_result(booking_id, payment, refund, fee_cents, status) -> dict:
        return {
            "booking_id": booking_id,
            "status": status,
            "payment_id": payment.id if payment else None,
            "payment_status": payment.status if payment else None,
            "refund_id": refund.id if refund else None,
            "refund_cents": refund.amount_cents if refund else 0,
            "refund_status": refund.status if refund else None,
            "fee_cents": fee_cents,
        }

    async def booking_payment_status(self, db: AsyncSession, booking_id: str) -> str:
        """How the booking's payment stands for booking_service: UNPAID, PAID, REFUNDED or PARTIALLY_REFUNDED.

        Only the payment the booking kept counts; a duplicate paid and refunded leaves the booking PAID.
        """
        result = await db.execute(
            select(Payment.status).where(Payment.booking_id == booking_id, Payment.purpose == BOOKING)
        )
        statuses = set(result.scalars().all())
        for status, shown in (
            ("COMPLETED", "PAID"),
            ("PARTIALLY_REFUNDED", "PARTIALLY_REFUNDED"),
            ("REFUNDED", "REFUNDED"),
        ):
            if status in statuses:
                return shown
        return "UNPAID"

    async def payments_by_payer(
        self, db: AsyncSession, payer_id: str, limit: int = 100, purpose: str = BOOKING
    ) -> List[Payment]:
        result = await db.execute(
            select(Payment)
            .where(Payment.payer_id == payer_id, Payment.purpose == purpose)
            .order_by(Payment.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def payments_for_booking(self, db: AsyncSession, booking_id: str, purpose: str = BOOKING) -> List[Payment]:
        """The booking's own payments (by default), or with purpose TIP its tips."""
        result = await db.execute(
            select(Payment)
            .where(Payment.booking_id == booking_id, Payment.purpose == purpose)
            .order_by(Payment.created_at)
        )
        return list(result.scalars().all())

    async def get_refund(self, db: AsyncSession, refund_id: str) -> Optional[Refund]:
        return await db.get(Refund, refund_id)

    async def refund_by_key(self, db: AsyncSession, key: str) -> Optional[Refund]:
        return (await db.execute(select(Refund).where(Refund.idempotency_key == key))).scalar_one_or_none()

    async def refunded_cents(self, db: AsyncSession, payment_id: str) -> int:
        return await self._refunded_cents(db, payment_id)

    async def payment_by_key(self, db: AsyncSession, idempotency_key: str) -> Optional[Payment]:
        result = await db.execute(select(Payment).where(Payment.idempotency_key == idempotency_key))
        return result.scalar_one_or_none()

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
