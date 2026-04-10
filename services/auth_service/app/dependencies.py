from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.security import decode_token
from app.database import get_db
import redis.asyncio as aioredis
from app.config import settings

security = HTTPBearer()


async def get_redis():
    client = aioredis.from_url(settings.REDIS_URL)
    try:
        yield client
    finally:
        await client.close()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db=Depends(get_db),
):
    token = credentials.credentials
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
