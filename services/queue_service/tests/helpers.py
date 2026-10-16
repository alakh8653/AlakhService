"""Shared test helpers: signed tokens, a notifier that records what it sends, joining a queue."""

from jose import jwt

from app.config import settings


def auth(sub: str, role: str = "user", token_type: str = "access") -> dict:
    token = jwt.encode(
        {"sub": sub, "role": role, "type": token_type}, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return {"Authorization": f"Bearer {token}"}


ALICE, BOB, ADMIN = auth("alice"), auth("bob"), auth("ops", "admin")
CALLED: list = []


class RecordingNotifier:
    async def send(self, event, recipients, data):
        CALLED.append((event, [r["user_id"] for r in recipients]))


async def join(client, qid, who):
    resp = await client.post(
        f"/api/v1/queues/{qid}/join", json={"customer_id": who, "service_id": "svc-1"}, headers=auth(who)
    )
    assert resp.status_code == 201
    return resp.json()
