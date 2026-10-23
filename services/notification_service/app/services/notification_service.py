import asyncio
import json
import math
from datetime import datetime, timezone
from typing import List, Optional

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.channels.email import EmailChannel
from app.channels.in_app import InAppChannel
from app.channels.msg91 import MSG91SMSChannel
from app.channels.push import FCMChannel
from app.channels.sms import TwilioSMSChannel
from app.config import settings
from app.core.contact import fetch_contact
from app.core.events import CRITICAL_EVENTS, SHOP_EMAIL_EVENTS, render_sms
from app.core.events import render as render_event
from app.core.exceptions import NotificationNotFoundError, TemplateNotFoundError
from app.models.notification import DeviceToken, Notification, NotificationPreference, NotificationTemplate
from app.schemas.notification import NotificationListResponse
from app.services.template_service import template_service

log = structlog.get_logger()

CHANNEL_FALLBACK = ["push", "in_app", "email", "sms"]


class NotificationService:
    _fcm: Optional[FCMChannel] = None

    def _get_fcm(self) -> FCMChannel:
        # One channel per process so the OAuth token is reused until it expires.
        if self._fcm is None:
            self._fcm = FCMChannel.from_settings(settings.FCM_SERVICE_ACCOUNT_JSON, settings.FCM_SERVICE_ACCOUNT_FILE)
        return self._fcm

    def _get_sms(self) -> TwilioSMSChannel:
        return TwilioSMSChannel(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN, settings.TWILIO_FROM_NUMBER)

    def _get_email(self) -> EmailChannel:
        return EmailChannel(
            settings.SMTP_HOST,
            settings.SMTP_PORT,
            settings.SMTP_USERNAME,
            settings.SMTP_PASSWORD,
            settings.SMTP_FROM_EMAIL,
            settings.SMTP_FROM_NAME,
            settings.SMTP_USE_TLS,
        )

    def _get_msg91(self) -> MSG91SMSChannel:
        return MSG91SMSChannel(settings.MSG91_AUTH_KEY, settings.MSG91_SENDER_ID, settings.MSG91_API_URL)

    @staticmethod
    def _msg91_template(event: str) -> str:
        # booking.confirmed -> MSG91_TEMPLATE_BOOKING_CONFIRMED
        return getattr(settings, "MSG91_TEMPLATE_" + event.upper().replace(".", "_"), "") or ""

    async def send_sms(self, to_number: str, body: str, event: str) -> bool:
        """Texts [body] through SMS_PROVIDER; with MSG91 only events that have a DLT template id."""
        provider = (settings.SMS_PROVIDER or "none").strip().lower()
        if provider == "msg91":
            return await self._get_msg91().send(to_number, body, self._msg91_template(event))
        if provider == "twilio" and settings.TWILIO_ACCOUNT_SID and settings.TWILIO_FROM_NUMBER:
            return await self._get_sms().send(to_number, body)
        return False

    async def send_email(self, to_email: str, subject: str, body: str) -> bool:
        if not settings.SMTP_HOST:
            return False
        return await self._get_email().send(to_email, subject, body)

    async def deliver_fallback(
        self, user_id: str, event: str, role: Optional[str], title: str, body: str, data: dict, pushed: bool
    ) -> Optional[str]:
        """SMS or email for people the app cannot reach, after the event is recorded. Returns the channel used.

        - A shop owner hears about every new booking, and the outcome of the shop's review, by email:
          the shop dashboard has no push.
        - Critical booking events (CRITICAL_EVENTS) go by SMS, or else email, to anyone with no push device.

        Messages go to the recipient's OWN phone/email and never contain anyone else's (events.scrub).
        """
        shop_email = event in SHOP_EMAIL_EVENTS and role == "shop"
        if not shop_email and (pushed or event not in CRITICAL_EVENTS):
            return None
        contact = await fetch_contact(user_id)
        if not contact:
            return None
        if not shop_email and contact.get("phone"):
            text = render_sms(event, data)
            if text and await self.send_sms(contact["phone"], text, event):
                return "sms"
        if contact.get("email"):
            email_body = f"{body}\n\n"
            if shop_email:
                action = "Please confirm or decline it" if event == "booking.created" else "See the details"
                email_body += f"{action} in your shop dashboard"
                email_body += f": {settings.SHOP_DASHBOARD_URL}\n" if settings.SHOP_DASHBOARD_URL else ".\n"
            else:
                email_body += "Open the AlakhService app for the details.\n"
            email_body += "\nThis is an automatic message from AlakhService; replies are not read.\n"
            if await self.send_email(contact["email"], f"AlakhService: {title}", email_body):
                return "email"
        log.info("notification_fallback_undelivered", notify_event=event, user_id=user_id)
        return None

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

    async def _get_enabled_channels(
        self, db: AsyncSession, user_id: str, requested_channels: Optional[List[str]]
    ) -> List[str]:
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

    async def _dispatch_channel(
        self,
        db: AsyncSession,
        redis,
        channel: str,
        user_id: str,
        notif: Notification,
        title: str,
        body: str,
        data: dict,
    ) -> bool:
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
            return await self.send_sms(to_number, body, data.get("event", ""))
        return False

    async def notify_event(
        self, db: AsyncSession, redis, user_id: str, event: str, role: Optional[str], data: dict
    ) -> Optional[Notification]:
        """Records an event's notification for one person and pushes it to their devices and open apps.

        The stored notification is what the app lists, so it is kept even if no live channel delivers.
        """
        rendered = render_event(event, role, data)
        if rendered is None:
            return None
        title, body = rendered
        payload = {"event": event, **{k: v for k, v in data.items() if v is not None}}
        notif = Notification(
            user_id=user_id,
            channel="in_app",
            status="SENT",
            title=title,
            body=body,
            data=json.dumps(payload),
            retry_count=0,
            sent_at=datetime.now(timezone.utc),
        )
        db.add(notif)
        await db.flush()
        if await self._dispatch_channel(db, redis, "push", user_id, notif, title, body, payload):
            notif.channel = "push"
        if redis is not None:
            await InAppChannel(redis).send(user_id, title, body, {**payload, "id": notif.id})
        await db.flush()
        return notif

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
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id, Notification.is_read == False)
        )
        return result.scalar_one()


notification_service = NotificationService()
