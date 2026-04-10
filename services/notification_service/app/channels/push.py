import httpx
import structlog

log = structlog.get_logger()

class FCMChannel:
    FCM_URL = "https://fcm.googleapis.com/fcm/send"
    
    def __init__(self, server_key: str):
        self.server_key = server_key
    
    async def send(self, device_token: str, title: str, body: str, data: dict = None) -> bool:
        headers = {
            "Authorization": f"key={self.server_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "to": device_token,
            "notification": {"title": title, "body": body},
            "data": data or {},
        }
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(self.FCM_URL, json=payload, headers=headers, timeout=10)
                result = resp.json()
                return result.get("success", 0) == 1
            except Exception as e:
                log.error("fcm_send_failed", error=str(e))
                return False
