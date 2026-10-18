"""Public reviews of shops: summaries, listing, owner replies, reports and moderation.

A review is a ShopRating (one per completed booking). Hidden reviews are left out of everything the
public sees, including the shop's average.
"""

from datetime import datetime, timezone
from typing import List, Optional, Sequence, Tuple

import structlog
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shop import ReviewReport, Shop, ShopRating
from app.schemas.review import (
    ModerationReview,
    OwnerReply,
    RatingSummary,
    ReviewResponse,
    ShopRatingBrief,
    StarCount,
)

log = structlog.get_logger()

# Shown when a reviewer's account had no usable name; every review comes from a completed booking.
ANONYMOUS_REVIEWER = "Verified customer"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _stars(rating: float) -> int:
    return min(5, max(1, int(round(rating))))


def _utc(value: Optional[datetime]) -> Optional[datetime]:
    """Times are stored in UTC; a database without time zones (SQLite) hands them back naive."""
    return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value


def to_response(review: ShopRating) -> ReviewResponse:
    reply = None
    if review.reply:
        reply = OwnerReply(
            text=review.reply,
            created_at=_utc(review.reply_created_at),
            updated_at=_utc(review.reply_updated_at or review.reply_created_at),
        )
    return ReviewResponse(
        id=review.id,
        shop_id=review.shop_id,
        service_id=review.service_id,
        rating=_stars(review.rating),
        comment=review.comment,
        reviewer_name=review.reviewer_name or ANONYMOUS_REVIEWER,
        created_at=_utc(review.created_at),
        reply=reply,
    )


class ReviewService:
    async def refresh_shop_rating(self, db: AsyncSession, shop_id: str) -> Shop:
        """Recompute the shop's average and count from its visible reviews."""
        avg, count = (
            await db.execute(
                select(func.avg(ShopRating.rating), func.count(ShopRating.id)).where(
                    ShopRating.shop_id == shop_id,
                    ShopRating.is_hidden == False,  # noqa: E712
                )
            )
        ).one()
        shop = (await db.execute(select(Shop).where(Shop.id == shop_id))).scalar_one()
        shop.rating_count = count or 0
        shop.rating_avg = float(avg or 0.0)
        await db.flush()
        return shop

    async def summary(self, db: AsyncSession, shop_id: str, service_id: Optional[str] = None) -> RatingSummary:
        stmt = (
            select(ShopRating.rating, func.count(ShopRating.id))
            .where(ShopRating.shop_id == shop_id, ShopRating.is_hidden == False)  # noqa: E712
            .group_by(ShopRating.rating)
        )
        if service_id:
            stmt = stmt.where(ShopRating.service_id == service_id)
        counts = {s: 0 for s in range(1, 6)}
        total = 0
        for rating, count in (await db.execute(stmt)).all():
            counts[_stars(rating)] += count
            total += rating * count
        n = sum(counts.values())
        return RatingSummary(
            shop_id=shop_id,
            service_id=service_id,
            average_rating=round(total / n, 1) if n else 0.0,
            review_count=n,
            distribution=[StarCount(stars=s, count=counts[s]) for s in range(5, 0, -1)],
        )

    async def briefs(self, db: AsyncSession, shop_ids: Sequence[str]) -> List[ShopRatingBrief]:
        """Average and count for each of several shops (service cards show their shop's rating)."""
        if not shop_ids:
            return []
        rows = (
            await db.execute(select(Shop.id, Shop.rating_avg, Shop.rating_count).where(Shop.id.in_(shop_ids)))
        ).all()
        found = {
            sid: ShopRatingBrief(shop_id=sid, average_rating=round(avg, 1) if count else 0.0, review_count=count)
            for sid, avg, count in rows
        }
        return [found[sid] for sid in dict.fromkeys(shop_ids) if sid in found]

    async def list_reviews(
        self,
        db: AsyncSession,
        shop_id: str,
        skip: int = 0,
        limit: int = 10,
        rating: Optional[int] = None,
        service_id: Optional[str] = None,
        needs_reply: bool = False,
    ) -> Tuple[List[ShopRating], int]:
        """Visible reviews, newest first."""
        conditions = [ShopRating.shop_id == shop_id, ShopRating.is_hidden == False]  # noqa: E712
        if rating is not None:
            # Stored ratings are whole stars; the range also catches any older fractional ones.
            conditions += [ShopRating.rating >= rating - 0.5, ShopRating.rating < rating + 0.5]
        if service_id:
            conditions.append(ShopRating.service_id == service_id)
        if needs_reply:
            conditions.append(ShopRating.reply.is_(None))
        total = (await db.execute(select(func.count(ShopRating.id)).where(*conditions))).scalar_one()
        rows = await db.execute(
            select(ShopRating)
            .where(*conditions)
            .order_by(ShopRating.created_at.desc(), ShopRating.id.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(rows.scalars().all()), total

    async def get(self, db: AsyncSession, review_id: str, shop_id: Optional[str] = None) -> Optional[ShopRating]:
        review = (await db.execute(select(ShopRating).where(ShopRating.id == review_id))).scalar_one_or_none()
        if review is None or (shop_id is not None and review.shop_id != shop_id):
            return None
        return review

    async def set_reply(self, db: AsyncSession, review: ShopRating, text: str) -> ShopRating:
        now = _now()
        if not review.reply:
            review.reply_created_at = now
        review.reply = text
        review.reply_updated_at = now
        await db.flush()
        log.info("review_replied", review_id=review.id, shop_id=review.shop_id)
        return review

    async def delete_reply(self, db: AsyncSession, review: ShopRating) -> ShopRating:
        review.reply = None
        review.reply_created_at = None
        review.reply_updated_at = None
        await db.flush()
        return review

    async def report(self, db: AsyncSession, review: ShopRating, reporter_id: str, reason: str) -> bool:
        """Flag a review for moderation; False when this user had already reported it."""
        existing = await db.execute(
            select(ReviewReport.id).where(ReviewReport.review_id == review.id, ReviewReport.reporter_id == reporter_id)
        )
        if existing.scalar_one_or_none() is not None:
            return False
        try:
            async with db.begin_nested():
                db.add(ReviewReport(review_id=review.id, reporter_id=reporter_id, reason=reason, created_at=_now()))
        except IntegrityError:  # the same user reporting twice at once
            return False
        review.report_count = (review.report_count or 0) + 1
        await db.flush()
        log.info("review_reported", review_id=review.id, report_count=review.report_count)
        return True

    async def moderation_queue(
        self, db: AsyncSession, skip: int = 0, limit: int = 20, hidden: Optional[bool] = None
    ) -> Tuple[List[ModerationReview], int]:
        """Reported or hidden reviews, most reported first."""
        conditions = [(ShopRating.report_count > 0) | (ShopRating.is_hidden == True)]  # noqa: E712
        if hidden is not None:
            conditions.append(ShopRating.is_hidden == hidden)
        total = (await db.execute(select(func.count(ShopRating.id)).where(*conditions))).scalar_one()
        reviews = list(
            (
                await db.execute(
                    select(ShopRating)
                    .where(*conditions)
                    .order_by(ShopRating.report_count.desc(), ShopRating.created_at.desc(), ShopRating.id)
                    .offset(skip)
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        reasons: dict = {r.id: [] for r in reviews}
        if reviews:
            rows = await db.execute(
                select(ReviewReport.review_id, ReviewReport.reason)
                .where(ReviewReport.review_id.in_(list(reasons)))
                .order_by(ReviewReport.created_at)
            )
            for review_id, reason in rows.all():
                reasons[review_id].append(reason)
        return [self.to_moderation(r, reasons[r.id]) for r in reviews], total

    def to_moderation(self, review: ShopRating, reasons: List[str]) -> ModerationReview:
        return ModerationReview(
            **to_response(review).model_dump(),
            is_hidden=review.is_hidden,
            report_count=review.report_count or 0,
            report_reasons=reasons,
        )

    async def set_hidden(self, db: AsyncSession, review: ShopRating, hidden: bool) -> ShopRating:
        review.is_hidden = hidden
        await db.flush()
        await self.refresh_shop_rating(db, review.shop_id)
        log.info("review_visibility_changed", review_id=review.id, hidden=hidden)
        return review

    async def report_reasons(self, db: AsyncSession, review_id: str) -> List[str]:
        rows = await db.execute(
            select(ReviewReport.reason).where(ReviewReport.review_id == review_id).order_by(ReviewReport.created_at)
        )
        return list(rows.scalars().all())


review_service = ReviewService()
