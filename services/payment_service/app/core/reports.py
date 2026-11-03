"""Sends shops their reports through notification_service, and works out which reports are due.

Every morning after REPORT_HOUR_IST: yesterday's report; on Mondays last week's; on the 1st last month's; on
1 April the financial year just ended. One row per shop and report keeps a retried pass, or a second copy of
this service, from sending it twice. A shop with nothing recorded in the period gets nothing.
"""

import asyncio
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Tuple

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.core.money import IST
from app.core.peers import ShopDirectory, get_shop_directory
from app.models.payment import ShopCashEntry, ShopEarning, ShopReportDelivery
from app.services import report_service

log = structlog.get_logger()


class ReportSender:
    def __init__(self, base_url: str, key: str, transport: Optional[httpx.AsyncBaseTransport] = None):
        self.base_url = base_url
        self.key = key
        self._transport = transport

    async def send(self, payload: dict) -> Optional[List[str]]:
        """The channels it went out on, or None when notification_service could not take it."""
        if not self.key:
            return None
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=30.0, transport=self._transport) as client:
                resp = await client.post(
                    "/internal/notifications/report", json=payload, headers={"X-Internal-Key": self.key}
                )
        except httpx.HTTPError as e:
            log.warning("report_send_failed", error=str(e))
            return None
        if resp.status_code != 200:
            log.warning("report_send_rejected", status=resp.status_code)
            return None
        return resp.json().get("sent_to", [])


def get_report_sender() -> ReportSender:
    return ReportSender(settings.NOTIFICATION_SERVICE_URL, settings.INTERNAL_API_KEY)


async def send_report(
    shops: ShopDirectory, sender: ReportSender, shop_id: str, report: dict, prefs
) -> Optional[List[str]]:
    shop = await shops.shop(shop_id)
    if not shop or not shop.get("owner_id"):
        return None
    return await sender.send(
        {
            "user_id": shop["owner_id"],
            "shop_name": shop.get("name") or "",
            "email": bool(prefs.email),
            "whatsapp": bool(prefs.whatsapp),
            "report": {k: (v.isoformat() if isinstance(v, date) else v) for k, v in report.items()},
            "csv": report_service.to_csv(report),
        }
    )


def due_reports(now: datetime) -> List[Tuple[str, date]]:
    """(period, a day inside it) for each report due at this moment."""
    local = now.astimezone(IST)
    if local.hour < settings.REPORT_HOUR_IST:
        return []
    today = local.date()
    yesterday = today - timedelta(days=1)
    due = [("daily", yesterday)]
    if today.weekday() == 0:
        due.append(("weekly", yesterday))
    if today.day == 1:
        due.append(("monthly", yesterday))
    if today.month == 4 and today.day == 1:
        due.append(("yearly", yesterday))
    return due


async def _active_shops(db, start: date, end: date) -> List[str]:
    since = report_service.ist_start(start)
    until = report_service.ist_start(end + timedelta(days=1))
    earned = await db.execute(
        select(ShopEarning.shop_id)
        .where(ShopEarning.completed_at >= since, ShopEarning.completed_at < until)
        .distinct()
    )
    wrote = await db.execute(
        select(ShopCashEntry.shop_id).where(ShopCashEntry.on_date >= start, ShopCashEntry.on_date <= end).distinct()
    )
    return sorted({*earned.scalars().all(), *wrote.scalars().all()})


async def _claim(factory, shop_id: str, period: str, start: date) -> bool:
    async with factory() as db:
        db.add(
            ShopReportDelivery(
                shop_id=shop_id, period=period, period_start=start, created_at=datetime.now(timezone.utc)
            )
        )
        try:
            await db.commit()
            return True
        except IntegrityError:
            return False


async def _release(factory, shop_id: str, period: str, start: date) -> None:
    """It did not go out: the next pass tries again while the report is still due."""
    async with factory() as db:
        row = await db.get(ShopReportDelivery, (shop_id, period, start))
        if row is not None:
            await db.delete(row)
            await db.commit()


async def run_once(factory, shops: ShopDirectory, sender: ReportSender, now: Optional[datetime] = None) -> int:
    sent = 0
    for period, day in due_reports(now or datetime.now(timezone.utc)):
        start, end = report_service.period_range(period, day)
        async with factory() as db:
            active = await _active_shops(db, start, end)
        for shop_id in active:
            async with factory() as db:
                prefs = await report_service.preference(db, shop_id)
                if not getattr(prefs, period) or not (prefs.email or prefs.whatsapp):
                    continue
                report = await report_service.build(db, shop_id, period, day)
            if not await _claim(factory, shop_id, period, start):
                continue
            if await send_report(shops, sender, shop_id, report, prefs) is None:
                await _release(factory, shop_id, period, start)
            else:
                sent += 1
    if sent:
        log.info("shop_reports_sent", count=sent)
    return sent


async def run_forever(factory) -> None:
    log.info("report_worker_started", interval=settings.REPORT_WORKER_INTERVAL_SECONDS)
    while True:
        try:
            await run_once(factory, get_shop_directory(), get_report_sender())
        except asyncio.CancelledError:
            raise
        except Exception as e:  # a bad pass never stops the next one
            log.error("report_worker_failed", error=str(e))
        await asyncio.sleep(settings.REPORT_WORKER_INTERVAL_SECONDS)
