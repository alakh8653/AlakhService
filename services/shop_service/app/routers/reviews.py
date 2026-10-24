"""Reviews customers see when choosing a shop, the owner's replies, reports and admin moderation.

Reviews are written through POST /shops/{shop_id}/rating (one per completed booking).
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ShopNotFoundError
from app.database import get_db
from app.dependencies import Caller, ensure_owner, require_caller
from app.models.shop import ShopRating
from app.schemas.review import (
    ModerationPage,
    ModerationReview,
    RatingSummary,
    ReplyCreate,
    ReportCreate,
    ReviewPage,
    ReviewResponse,
    ShopRatingBrief,
    VisibilityUpdate,
)
from app.services.review_service import review_service, to_response
from app.services.shop_service import shop_service

router = APIRouter()

MAX_BRIEFS = 50


async def _shop(db: AsyncSession, shop_id: str):
    try:
        return await shop_service.get_shop(db, shop_id)
    except ShopNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


async def _review(db: AsyncSession, shop_id: str, review_id: str) -> ShopRating:
    review = await review_service.get(db, review_id, shop_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    return review


def require_admin(caller: Caller = Depends(require_caller)) -> Caller:
    if not caller.is_admin:
        raise HTTPException(status_code=403, detail="Admins only")
    return caller


# Declared before /shops/{shop_id} (this router is included first) so "ratings" is not read as an id.
@router.get("/shops/ratings", response_model=List[ShopRatingBrief])
async def shop_ratings(
    ids: str = Query(..., description="Comma-separated shop ids, at most 50"), db: AsyncSession = Depends(get_db)
):
    """The rating shown next to each of several shops, e.g. for a page of service cards."""
    shop_ids = [i.strip() for i in ids.split(",") if i.strip()]
    if len(shop_ids) > MAX_BRIEFS:
        raise HTTPException(status_code=422, detail=f"At most {MAX_BRIEFS} shops at a time")
    return await review_service.briefs(db, shop_ids)


@router.get("/shops/{shop_id}/reviews/summary", response_model=RatingSummary)
async def review_summary(shop_id: str, service_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    await _shop(db, shop_id)
    return await review_service.summary(db, shop_id, service_id)


@router.get("/shops/{shop_id}/reviews", response_model=ReviewPage)
async def list_reviews(
    shop_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=50),
    rating: Optional[int] = Query(None, ge=1, le=5),
    service_id: Optional[str] = None,
    needs_reply: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """Newest first. Reviewers appear by first name and last initial only."""
    await _shop(db, shop_id)
    items, total = await review_service.list_reviews(
        db, shop_id, skip=skip, limit=limit, rating=rating, service_id=service_id, needs_reply=needs_reply
    )
    return ReviewPage(items=[to_response(r) for r in items], total=total, skip=skip, limit=limit)


@router.put("/shops/{shop_id}/reviews/{review_id}/reply", response_model=ReviewResponse)
async def reply_to_review(
    shop_id: str,
    review_id: str,
    data: ReplyCreate,
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(require_caller),
):
    """The shop owner's one public reply to a review; sending it again edits it."""
    ensure_owner((await _shop(db, shop_id)).owner_id, caller)
    review = await _review(db, shop_id, review_id)
    return to_response(await review_service.set_reply(db, review, data.text))


@router.delete("/shops/{shop_id}/reviews/{review_id}/reply", response_model=ReviewResponse)
async def delete_reply(
    shop_id: str, review_id: str, db: AsyncSession = Depends(get_db), caller: Caller = Depends(require_caller)
):
    ensure_owner((await _shop(db, shop_id)).owner_id, caller)
    review = await _review(db, shop_id, review_id)
    return to_response(await review_service.delete_reply(db, review))


@router.post("/shops/{shop_id}/reviews/{review_id}/report", status_code=202)
async def report_review(
    shop_id: str,
    review_id: str,
    data: ReportCreate,
    response: Response,
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(require_caller),
):
    """Flag a review for an admin to look at. It stays visible until an admin hides it."""
    review = await _review(db, shop_id, review_id)
    if review.is_hidden:
        raise HTTPException(status_code=404, detail="Review not found")
    if not await review_service.report(db, review, caller.user_id, data.reason):
        response.status_code = 200  # already reported by this user; nothing more to do
    return {"status": "reported"}


@router.get("/reviews/reported", response_model=ModerationPage, dependencies=[Depends(require_admin)])
async def moderation_queue(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    hidden: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
):
    """Reported and hidden reviews, most reported first."""
    items, total = await review_service.moderation_queue(db, skip=skip, limit=limit, hidden=hidden)
    return ModerationPage(items=items, total=total, skip=skip, limit=limit)


@router.put("/reviews/{review_id}/visibility", response_model=ModerationReview, dependencies=[Depends(require_admin)])
async def set_visibility(review_id: str, data: VisibilityUpdate, db: AsyncSession = Depends(get_db)):
    """Hide a review (it leaves the shop's listing and average) or put it back."""
    review = await review_service.get(db, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    await review_service.set_hidden(db, review, data.hidden)
    return review_service.to_moderation(review, await review_service.report_reasons(db, review.id))
