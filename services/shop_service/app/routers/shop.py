from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.database import get_db
from app.schemas.shop import ShopCreate, ShopUpdate, ShopResponse, RatingUpdate
from app.services.shop_service import shop_service
from app.core.exceptions import ShopNotFoundError

router = APIRouter()


@router.post("/shops", response_model=ShopResponse, status_code=201)
async def create_shop(data: ShopCreate, db: AsyncSession = Depends(get_db)):
    return await shop_service.create_shop(db, data)


@router.get("/shops", response_model=List[ShopResponse])
async def list_shops(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    return await shop_service.list_shops(db, skip=skip, limit=limit)


@router.get("/shops/search", response_model=List[ShopResponse])
async def search_shops(
    q: Optional[str] = None,
    city: Optional[str] = None,
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    return await shop_service.search_shops(db, q=q, city=city, category=category)


@router.get("/shops/{shop_id}", response_model=ShopResponse)
async def get_shop(shop_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await shop_service.get_shop(db, shop_id)
    except ShopNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/shops/{shop_id}", response_model=ShopResponse)
async def update_shop(shop_id: str, data: ShopUpdate, db: AsyncSession = Depends(get_db)):
    try:
        return await shop_service.update_shop(db, shop_id, data)
    except ShopNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/shops/{shop_id}", status_code=204)
async def delete_shop(shop_id: str, db: AsyncSession = Depends(get_db)):
    try:
        await shop_service.delete_shop(db, shop_id)
    except ShopNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/shops/{shop_id}/rating")
async def update_rating(shop_id: str, data: RatingUpdate, db: AsyncSession = Depends(get_db)):
    try:
        return await shop_service.update_rating(db, shop_id, data.rating)
    except ShopNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
