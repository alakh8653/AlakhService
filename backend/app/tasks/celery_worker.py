from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "alakhservice",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.celery_worker"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
    beat_schedule={
        "cleanup-expired-tokens-daily": {
            "task": "app.tasks.celery_worker.cleanup_expired_tokens",
            "schedule": crontab(hour=2, minute=0),
        },
    },
)


@celery_app.task(bind=True, max_retries=3)
def send_email_task(self, to_email: str, subject: str, html_body: str) -> None:
    """Celery task to send an email asynchronously."""
    import asyncio
    from app.utils.email import send_email
    try:
        asyncio.run(send_email(to_email, subject, html_body))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(bind=True, max_retries=3)
def send_push_notification_task(
    self, device_token: str, title: str, body: str, data: dict | None = None
) -> None:
    """Celery task to send a push notification via FCM asynchronously."""
    import asyncio
    from app.services.notification_service import send_push_notification
    try:
        asyncio.run(send_push_notification(device_token, title, body, data))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)


@celery_app.task(bind=True, max_retries=3)
def process_payment_callback_task(self, payload: dict) -> None:
    """Celery task to process a payment gateway callback in the background."""
    # TODO: deserialize payload, call payment_service.handle_webhook
    pass


@celery_app.task
def cleanup_expired_tokens() -> None:
    """Periodic task: remove expired tokens / stale records from the database."""
    # TODO: implement DB cleanup logic
    pass
