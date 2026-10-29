"""Keeps service_catalog's listing of each shop's services in line with the shop, whatever was missed.

Approving, rejecting, switching off or deleting a shop tells service_catalog right away (Reporter.
sync_listing), but that is best effort: if the message is lost, a hidden shop's services would stay
bookable. So every LISTING_RESYNC_SECONDS each shop's listing is sent again; service_catalog changes only
the services whose listing differs, so a pass where nothing was missed changes nothing.
"""

import asyncio

import structlog
from sqlalchemy import select

from app.config import settings
from app.models.shop import Shop
from app.services.shop_service import is_public

log = structlog.get_logger()

# The first pass waits this long after start, so service_catalog is up when the stack starts together.
FIRST_PASS_DELAY_SECONDS = 30


async def resync_all(factory, reporter) -> int:
    """Sends every shop's listing (listed only while approved and switched on); returns how many."""
    async with factory() as db:
        shops = [(s.id, is_public(s)) for s in (await db.execute(select(Shop))).scalars().all()]
    for shop_id, listed in shops:
        await reporter.sync_listing(shop_id, listed)
    return len(shops)


async def run_forever(factory, reporter) -> None:
    log.info("listing_resync_started", interval=settings.LISTING_RESYNC_SECONDS)
    await asyncio.sleep(FIRST_PASS_DELAY_SECONDS)
    while True:
        try:
            log.info("listing_resync_pass", shops=await resync_all(factory, reporter))
        except asyncio.CancelledError:
            raise
        except Exception as e:  # a bad pass never stops the next one
            log.error("listing_resync_failed", error=str(e))
        await asyncio.sleep(settings.LISTING_RESYNC_SECONDS)
