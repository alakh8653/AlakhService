import asyncio
import json
import math
from datetime import datetime, timezone
from typing import List, Optional
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func

from app.models.notification import Notification, NotificationTemplate, NotificationPreference, DeviceToken
from app.schemas.notification import NotificationCreate, NotificationListResponse, NotificationResponse
from app.channels.push import FCMChannel
from app.channels.sms import TwilioSMSChannel
from app.channels.email import EmailChannel
from app.channels.in_app import InAppChannel
from app.services.template_service import template_service
from app.core.exceptions import TemplateNotFoundError, NotificationNotFoundError
from app.config import settings

log = structlog.get_logger()

CHANNEL_FALLBACK = ["push", "in_app", "email", "sms"]

class NotificationService:
    def _get_fcm(self) -> FCMChannel:
        return FCMChannel(settings.FCM_SERVER_KEY)

    def _get_sms(self) -> TwilioSMSChannel:
        return TwilioSMSChannel(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN, settings.TWILIO_FROM_NUMBER)

    def _get_email(self) -> EmailChannel:
        return EmailChannel(settings.SMTP_HOST, settings.SMTP_PORT, settings.SMTP_USERNAME, settings.SMTP_PASSWORD, settings.SMTP_FROM_EMAIL, settings.SMTP_FROM_NAME)

    async def check_quiet_hours(self, db: AsyncSession, user_id: str) -> bool:
        now_hour = datetime.now(timezone.utc).hour
        result = await db.execute(
            select(NotificationPreference).where(
                NotificationPreference.user_id == user_id,
                NotificationPreference.quiet_hours_start.isnot(None),
                NotificationPreference.quiet_hours_end.isnot(None),
            )
        )
        prefs = result.scalars().all()
        for pref in prefs:
            start = pref.quiet_hours_start
            end = pref.quiet_hours_end
            if start <= end:
                if start <= now_hour < end:
                    return True
            else:
                if now_hour >= start or now_hour < end:
                    return True
        return False

    async def _get_enabled_channels(self, db: AsyncSession, user_id: str, requested_channels: Optional[List[str]]) -> List[str]:
        result = await db.execute(
            select(NotificationPreference).where(
                NotificationPreference.user_id == user_id,
                NotificationPreference.is_enabled == True,
            )
        )
        enabled = {p.channel for p in result.scalars().all()}
        candidates = requested_channels or CHANNEL_FALLBACK
        return [c for c in candidates if c in enabled] or candidates

    async def send(
        self,
        db: AsyncSession,
        redis,
        user_id: str,
        template_name: str,
        variables: dict,
        channels: Optional[List[str]] = None,
        priority: str = "normal",
    ) -> Notification:
        result = await db.execute(
            select(NotificationTemplate).where(
                NotificationTemplate.name == template_name,
                NotificationTemplate.is_active == True,
            )
        )
        tmpl = result.scalar_one_or_none()
        if not tmpl:
            raise TemplateNotFoundError(f"Template '{template_name}' not found")

        missing = template_service.validate_template_variables(tmpl, variables)
        if missing:
            raise ValueError(f"Missing template variables: {missing}")

        rendered = template_service.render_template(tmpl, variables)
        title = rendered["title"] or tmpl.name
        body = rendered["body"]

        active_channels = await self._get_enabled_channels(db, user_id, channels or [tmpl.channel])

        notif = Notification(
            user_id=user_id,
            channel=active_channels[0] if active_channels else tmpl.channel,
            template_id=tmpl.id,
            status="PENDING",
            title=title,
            body=body,
            data=json.dumps(variables),
            retry_count=0,
        )
        db.add(notif)
        await db.flush()

        sent = False
        for attempt in range(1, settings.MAX_RETRY_ATTEMPTS + 1):
            for channel in active_channels:
                sent = await self._dispatch_channel(db, redis, channel, user_id, notif, title, body, variables)
                if sent:
                    notif.channel = channel
                    break
            if sent:
                break
            delay = settings.RETRY_BASE_DELAY * math.pow(2, attempt - 1)
            log.warning("notification_retry", notif_id=notif.id, attempt=attempt, delay=delay)
            await asyncio.sleep(delay)
            notif.retry_count = attempt

        if sent:
            notif.status = "SENT"
            notif.sent_at = datetime.now(timezone.utc)
        else:
            notif.status = "FAILED"
            notif.failed_reason = "All channels failed after retries"

        await db.flush()
        return notif

    async def _dispatch_channel(self, db: AsyncSession, redis, channel: str, user_id: str, notif: Notification, title: str, body: str, data: dict) -> bool:
        if channel == "push":
            result = await db.execute(
                select(DeviceToken).where(DeviceToken.user_id == user_id, DeviceToken.is_active == True)
            )
            tokens = result.scalars().all()
            if not tokens:
                return False
            fcm = self._get_fcm()
            results = await asyncio.gather(*[fcm.send(t.token, title, body, data) for t in tokens])
            return any(results)
        elif channel == "in_app":
            if redis:
                in_app = InAppChannel(redis)
                return await in_app.send(user_id, title, body, data)
            return False
        elif channel == "email":
            to_email = data.get("email") or data.get("to_email")
            if not to_email:
                return False
            email_ch = self._get_email()
            return await email_ch.send(to_email, title, body)
        elif channel == "sms":
            to_number = data.get("phone") or data.get("to_number")
            if not to_number:
                return False
            sms_ch = self._get_sms()
            return await sms_ch.send(to_number, body)
        return False

    async def get_notifications(
        self, db: AsyncSession, user_id: str, unread_only: bool = False, page: int = 1, per_page: int = 20
    ) -> NotificationListResponse:
        q = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            q = q.where(Notification.is_read == False)
        q = q.order_by(Notification.created_at.desc())
        count_q = select(func.count()).select_from(Notification).where(Notification.user_id == user_id)
        if unread_only:
            count_q = count_q.where(Notification.is_read == False)
        total_result = await db.execute(count_q)
        total = total_result.scalar_one()
        q = q.offset((page - 1) * per_page).limit(per_page)
        result = await db.execute(q)
        items = result.scalars().all()
        return NotificationListResponse(items=items, total=total, page=page, per_page=per_page)

    async def mark_as_read(self, db: AsyncSession, notification_id: str, user_id: str) -> bool:
        result = await db.execute(
            select(Notification).where(Notification.id == notification_id, Notification.user_id == user_id)
        )
        notif = result.scalar_one_or_none()
        if not notif:
            raise NotificationNotFoundError(f"Notification {notification_id} not found")
        notif.is_read = True
        await db.flush()
        return True

    async def mark_all_read(self, db: AsyncSession, user_id: str) -> int:
        result = await db.execute(
            update(Notification)
            .where(Notification.user_id == user_id, Notification.is_read == False)
            .values(is_read=True)
            .returning(Notification.id)
        )
        return len(result.fetchall())

    async def get_unread_count(self, db: AsyncSession, user_id: str) -> int:
        result = await db.execute(
            select(func.count()).select_from(Notification).where(
                Notification.user_id == user_id, Notification.is_read == False
            )
        )
        return result.scalar_one()

notification_service = NotificationService()
