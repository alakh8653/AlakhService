"""Every shop's listing is sent to service_catalog again now and then, so a missed change is put right."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models.shop  # noqa: F401
from app.config import settings
from app.core.listing_sync import resync_all
from app.database import Base
from app.models.shop import APPROVED, PENDING_REVIEW, Shop


class FakeReporter:
    def __init__(self):
        self.sent = []

    async def sync_listing(self, shop_id, listed):
        self.sent.append((shop_id, listed))


@pytest.mark.asyncio
async def test_each_shop_is_listed_only_while_approved_and_switched_on():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        db.add_all(
            [
                Shop(id="live", owner_id="o", name="Live", category="salon", verification_status=APPROVED),
                Shop(
                    id="off", owner_id="o", name="Off", category="salon", verification_status=APPROVED, is_active=False
                ),
                Shop(id="new", owner_id="o", name="New", category="salon", verification_status=PENDING_REVIEW),
            ]
        )
        await db.commit()
    reporter = FakeReporter()
    assert await resync_all(factory, reporter) == 3
    assert sorted(reporter.sent) == [("live", True), ("new", False), ("off", False)]
    await engine.dispose()


def test_the_resync_is_off_under_tests():
    assert settings.LISTING_RESYNC_SECONDS == 0
