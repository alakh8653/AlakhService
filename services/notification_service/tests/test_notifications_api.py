"""Users only reach their own notifications; sending and templates are for admins."""

import asyncio
import json
import threading
import time
from collections import deque

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import app.models.notification  # noqa: F401
import app.routers.notifications as notifications_router
from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models.notification import Notification


def token(sub: str, role: str = "user", token_type: str = "access") -> str:
    return jwt.encode({"sub": sub, "role": role, "type": token_type}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def auth(sub: str, role: str = "user", token_type: str = "access") -> dict:
    return {"Authorization": f"Bearer {token(sub, role, token_type)}"}


@pytest_asyncio.fixture
async def client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        db.add_all(
            [
                Notification(
                    id="n-alice", user_id="alice", channel="in_app", title="Hi", body="For Alice", status="sent"
                ),
                Notification(id="n-bob", user_id="bob", channel="in_app", title="Hi", body="For Bob", status="sent"),
            ]
        )
        await db.commit()

    async def override_get_db():
        async with factory() as session:
            yield session
            await session.commit()

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_users_see_only_their_own_notifications(client):
    assert (await client.get("/api/v1/notifications/me")).status_code == 401
    assert (
        await client.get("/api/v1/notifications/me", headers=auth("alice", token_type="refresh"))
    ).status_code == 401

    mine = (await client.get("/api/v1/notifications/me", headers=auth("alice"))).json()
    assert [n["id"] for n in mine["items"]] == ["n-alice"]
    assert (
        await client.get("/api/v1/notifications/me", params={"user_id": "bob"}, headers=auth("alice"))
    ).status_code == 403
    assert (
        await client.get("/api/v1/notifications/count/unread", params={"user_id": "bob"}, headers=auth("alice"))
    ).status_code == 403
    assert (
        await client.post("/api/v1/notifications/read-all", params={"user_id": "bob"}, headers=auth("alice"))
    ).status_code == 403
    # Bob's notification is not Alice's to mark read.
    assert (await client.post("/api/v1/notifications/n-bob/read", headers=auth("alice"))).status_code == 404

    support = await client.get("/api/v1/notifications/me", params={"user_id": "bob"}, headers=auth("ops", "admin"))
    assert [n["id"] for n in support.json()["items"]] == ["n-bob"]


@pytest.mark.asyncio
async def test_sending_and_templates_are_admin_only(client):
    body = {"user_id": "bob", "template_name": "welcome"}
    assert (await client.post("/api/v1/notifications/send", json=body, headers=auth("alice"))).status_code == 403
    template = {"name": "welcome", "channel": "in_app", "body_template": "Hello"}
    assert (
        await client.post("/api/v1/notifications/templates", json=template, headers=auth("alice"))
    ).status_code == 403
    assert (
        await client.post("/api/v1/notifications/templates", json=template, headers=auth("ops", "admin"))
    ).status_code == 201


@pytest.mark.asyncio
async def test_device_tokens_follow_the_signed_in_user(client):
    body = {"user_id": "bob", "token": "device-1", "platform": "android"}
    assert (
        await client.post("/api/v1/notifications/device-tokens", json=body, headers=auth("alice"))
    ).status_code == 403
    assert (await client.post("/api/v1/notifications/device-tokens", json=body, headers=auth("bob"))).json()[
        "user_id"
    ] == "bob"
    # The same device later signs in as Alice: it is now hers.
    moved = await client.post(
        "/api/v1/notifications/device-tokens", json={**body, "user_id": "alice"}, headers=auth("alice")
    )
    assert moved.json()["user_id"] == "alice"


def test_websocket_requires_the_users_own_token():
    with TestClient(app) as tc:
        for url in ("/api/v1/ws/notifications/bob", f"/api/v1/ws/notifications/bob?token={token('alice')}"):
            with pytest.raises(WebSocketDisconnect) as exc:
                with tc.websocket_connect(url) as ws:
                    ws.receive_json()
            assert exc.value.code in (1008, 1000)


class FakePubSub:
    def __init__(self):
        self.pending: deque[str] = deque()
        self.released = threading.Event()
        self.subscribed: set[str] = set()
        self.closed = False

    async def subscribe(self, channel):
        self.subscribed.add(channel)

    async def unsubscribe(self, channel):
        self.subscribed.discard(channel)

    async def aclose(self):
        self.closed = True

    async def listen(self):
        # Like Redis, this waits for messages indefinitely; `released` only lets a stuck handler finish.
        while not self.released.is_set():
            if self.pending:
                yield {"type": "message", "data": self.pending.popleft()}
            else:
                await asyncio.sleep(0.01)


class FakeRedis:
    def __init__(self, pubsub):
        self._pubsub = pubsub

    def pubsub(self):
        return self._pubsub

    async def aclose(self):
        pass


def test_websocket_subscription_ends_when_the_client_leaves(monkeypatch):
    pubsub = FakePubSub()
    monkeypatch.setattr(notifications_router.aioredis, "from_url", lambda *a, **kw: FakeRedis(pubsub))
    with TestClient(app) as tc:
        session = tc.websocket_connect(f"/api/v1/ws/notifications/alice?token={token('alice')}")
        ws = session.__enter__()
        try:
            pubsub.pending.append(json.dumps({"title": "Hi"}))
            assert ws.receive_json() == {"title": "Hi"}
            ws.close()
            deadline = time.monotonic() + 2
            while not pubsub.closed and time.monotonic() < deadline:
                time.sleep(0.01)
            assert pubsub.subscribed == set()
            assert pubsub.closed
        finally:
            pubsub.released.set()
            session.__exit__(None, None, None)


@pytest.mark.asyncio
async def test_templates_cannot_reach_python_internals(client):
    admin = auth("ops", "admin")
    escape = "{{ cycler.__init__.__globals__.os.getpid() }}"
    created = await client.post(
        "/api/v1/notifications/templates",
        json={"name": "evil", "channel": "in_app", "body_template": escape},
        headers=admin,
    )
    assert created.status_code == 201
    sent = await client.post(
        "/api/v1/notifications/send", json={"user_id": "bob", "template_name": "evil"}, headers=admin
    )
    assert sent.status_code == 422
    assert "unsafe" in sent.json()["detail"]

    broken = await client.post(
        "/api/v1/notifications/templates",
        json={"name": "broken", "channel": "in_app", "body_template": "{% if %}"},
        headers=admin,
    )
    assert broken.status_code == 422
