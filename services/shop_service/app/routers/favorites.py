"""Shops a customer has saved, to find and book them again quickly.

Included before the shop router, so /shops/favorites is not taken for a shop id.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import Caller, require_caller
from app.models.shop import APPROVED, FavoriteShop, Shop
from app.routers.shop import for_caller
from app.schemas.shop import ShopResponse
from app.services.shop_service import is_public

router = APIRouter()

# Plenty for anyone's regular places; stops one account from filling the table.
MAX_FAVORITES = 200


@router.get("/shops/favorites", response_model=List[ShopResponse])
async def list_favorites(db: AsyncSession = Depends(get_db), caller: Caller = Depends(require_caller)):
    """The caller's saved shops, most recently saved first. A shop that is closed or under review is
    left out until it is listed again, and stays saved."""
    result = await db.execute(
        select(Shop)
        .join(FavoriteShop, FavoriteShop.shop_id == Shop.id)
        .where(FavoriteShop.user_id == caller.user_id, Shop.is_active.is_(True), Shop.verification_status == APPROVED)
        .order_by(FavoriteShop.created_at.desc(), FavoriteShop.id)
    )
    return [for_caller(shop, caller) for shop in result.scalars().all()]


@router.put("/shops/{shop_id}/favorite", status_code=204)
async def add_favorite(shop_id: str, db: AsyncSession = Depends(get_db), caller: Caller = Depends(require_caller)):
    """Saves the shop. Saving it again changes nothing."""
    shop = await db.get(Shop, shop_id)
    if shop is None or not is_public(shop):
        raise HTTPException(status_code=404, detail="Shop not found")
    existing = await db.execute(
        select(FavoriteShop.id).where(FavoriteShop.user_id == caller.user_id, FavoriteShop.shop_id == shop_id)
    )
    if existing.scalar_one_or_none() is None:
        count = await db.execute(select(func.count()).where(FavoriteShop.user_id == caller.user_id))
        if (count.scalar() or 0) >= MAX_FAVORITES:
            raise HTTPException(status_code=409, detail=f"You can save up to {MAX_FAVORITES} shops")
        db.add(FavoriteShop(user_id=caller.user_id, shop_id=shop_id))
        try:
            await db.commit()
        except IntegrityError:  # the same save from another request got there first
            await db.rollback()
    return Response(status_code=204)


@router.delete("/shops/{shop_id}/favorite", status_code=204)
async def remove_favorite(shop_id: str, db: AsyncSession = Depends(get_db), caller: Caller = Depends(require_caller)):
    """Unsaves the shop. Unsaving one that is not saved changes nothing."""
    await db.execute(
        delete(FavoriteShop).where(FavoriteShop.user_id == caller.user_id, FavoriteShop.shop_id == shop_id)
    )
    await db.commit()
    return Response(status_code=204)
