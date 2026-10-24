"""Shop records for other platform services (X-Internal-Key); never routed by the gateway."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ShopNotFoundError
from app.core.internal import require_internal
from app.database import get_db
from app.schemas.shop import InternalShopResponse, PayoutDetailsOut
from app.services.kyc_service import kyc_service
from app.services.shop_service import shop_service

router = APIRouter(prefix="/internal", dependencies=[Depends(require_internal)])


@router.get("/shops/{shop_id}", response_model=InternalShopResponse)
async def internal_shop(shop_id: str, db: AsyncSession = Depends(get_db)):
    """The whole record, whatever its status: invoices need the legal name, address and GSTIN."""
    try:
        return await shop_service.get_shop(db, shop_id)
    except ShopNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/shops/{shop_id}/payout-details", response_model=PayoutDetailsOut)
async def internal_payout_details(shop_id: str, db: AsyncSession = Depends(get_db)):
    """Unmasked, for payment_service's payout export only."""
    details = await kyc_service.get_payout_details(db, shop_id)
    if details is None:
        raise HTTPException(status_code=404, detail="No payout details for this shop")
    return PayoutDetailsOut.model_validate(details)
