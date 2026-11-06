"""What happens to a business when its owner deletes their account.

Otherwise it would stay bookable with nobody to run it, and their ID and bank details would stay with us. The
upcoming bookings are cancelled and refunded, and it leaves the listings. PAN, Aadhaar and other documents, bank or
UPI details, photos and contact details are erased. The legal name, GSTIN and address stay: invoices already issued
print them and must be kept.

Refused, changing nothing, while a job is being served or the owner is still owed money: once the bank details are
gone it could not be paid.
"""

import httpx
import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.reporting import Reporter, get_reporter
from app.core.storage import LocalDocumentStorage, get_storage
from app.database import get_db
from app.dependencies import (
    Caller,
    ShopBookingCanceller,
    cancel_bookings_made_meanwhile,
    get_shop_booking_canceller,
    path_segment,
    require_caller,
)
from app.models.shop import Shop, ShopDocument, ShopPayoutDetails, ShopWorkPhoto

router = APIRouter()
log = structlog.get_logger()


class PaymentPeer:
    """payment_service: what a shop is still owed, and clearing its owner's own bookkeeping."""

    async def _post(self, client: httpx.AsyncClient, path: str) -> httpx.Response:
        return await client.post(path, headers={"X-Internal-Key": settings.INTERNAL_API_KEY})

    async def owed_cents(self, shop_id: str) -> int:
        """Raises when it cannot be asked: without knowing, the bank details must stay."""
        if not settings.INTERNAL_API_KEY:
            return 0
        try:
            async with httpx.AsyncClient(base_url=settings.PAYMENT_SERVICE_URL, timeout=10.0) as client:
                resp = await client.get(
                    f"/internal/payments/shops/{path_segment(shop_id)}/owed",
                    headers={"X-Internal-Key": settings.INTERNAL_API_KEY},
                )
        except httpx.HTTPError as e:
            raise HTTPException(status_code=503, detail="Please try again in a minute") from e
        if resp.status_code != 200:
            raise HTTPException(status_code=503, detail="Please try again in a minute")
        return int(resp.json().get("owed_cents") or 0)

    async def forget(self, shop_id: str) -> None:
        """Best effort, after the shop is closed."""
        if not settings.INTERNAL_API_KEY:
            return
        try:
            async with httpx.AsyncClient(base_url=settings.PAYMENT_SERVICE_URL, timeout=10.0) as client:
                resp = await self._post(client, f"/internal/payments/shops/{path_segment(shop_id)}/forget")
            if resp.status_code != 200:
                log.warning("shop_closure_forget_rejected", shop_id=shop_id, status=resp.status_code)
        except httpx.HTTPError as e:
            log.warning("shop_closure_forget_failed", shop_id=shop_id, error=str(e))


def get_payment_peer() -> PaymentPeer:
    return PaymentPeer()


@router.delete("/shops/mine", status_code=204)
async def close_my_shops(
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db, scope="function"),
    caller: Caller = Depends(require_caller),
    storage: LocalDocumentStorage = Depends(get_storage),
    cancel_bookings: ShopBookingCanceller = Depends(get_shop_booking_canceller),
    payments: PaymentPeer = Depends(get_payment_peer),
    reporter: Reporter = Depends(get_reporter),
):
    """Part of deleting an account (auth_service calls it as the person). Repeating it is safe."""
    shops = list((await db.execute(select(Shop).where(Shop.owner_id == caller.user_id))).scalars().all())
    for shop in shops:
        owed = await payments.owed_cents(shop.id)
        if owed > 0:
            raise HTTPException(
                status_code=409,
                detail=f"You are still owed ₹{owed / 100:,.2f} for {shop.name}. "
                "Please wait for your payout or contact support, then delete your account.",
            )
    # Every check first, and each shop's bookings next: a refusal leaves everything as it was.
    for shop in shops:
        await cancel_bookings(shop.id)
    keys = []
    for shop in shops:
        for model in (ShopDocument, ShopWorkPhoto):
            rows = (await db.execute(select(model).where(model.shop_id == shop.id))).scalars().all()
            keys += [row.storage_key for row in rows if row.storage_key]
            await db.execute(delete(model).where(model.shop_id == shop.id))
        await db.execute(delete(ShopPayoutDetails).where(ShopPayoutDetails.shop_id == shop.id))
        shop.is_active = False
        shop.phone = None
        shop.email = None
        shop.description = None
        shop.years_experience = None
        shop.languages = None
    await db.commit()
    # Files go once the records are gone for sure: a failed commit must not lose a live shop's documents.
    for key in keys:
        storage.delete(key)
    for shop in shops:
        background.add_task(reporter.sync_listing, shop.id, False)
        background.add_task(cancel_bookings_made_meanwhile, cancel_bookings, shop.id)
        background.add_task(payments.forget, shop.id)
    log.info("owner_shops_closed", user_id=caller.user_id, count=len(shops))
    return Response(status_code=204)
