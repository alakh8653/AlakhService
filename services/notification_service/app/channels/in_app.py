import json
import structlog
from typing import Optional

log = structlog.get_logger()

class InAppChannel:
    def __init__(self, redis_client):
        self.redis = redis_client

    async def send(self, user_id: str, title: str, body: str, data: dict = None) -> bool:
        try:
            payload = json.dumps({
                "type": "notification",
                "title": title,
                "body": body,
                "data": data or {},
            })
            channel = f"notifications:{user_id}"
            await self.redis.publish(channel, payload)
            log.info("in_app_notification_sent", user_id=user_id)
            return True
        except Exception as e:
            log.error("in_app_send_failed", error=str(e), user_id=user_id)
            return False
