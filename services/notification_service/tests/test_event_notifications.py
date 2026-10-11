"""Other services report booking and payment events; recipients get a notification they can read."""
import json

import httpx
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models.notification  # noqa: F401
from app.channels.push import FCMChannel
from app.config import settings
from app.core.events import render
from app.database import Base, get_db
from app.main import app
from app.routers.notifications import get_redis

KEY = "internal-test-key"


def auth(sub: str) -> dict:
    token = jwt.encode({"sub": sub, "role": "user", "type": "access"}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {"Authorization": f"Bearer {token}"}


class FakeRedis:
    def __init__(self):
        self.published = []

    async def publish(self, channel, payload):
        self.published.append((channel, json.loads(payload)))


@pytest_asyncio.fixture
async def client(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", KEY)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    redis = FakeRedis()

    async def override_get_db():
        async with factory() as session:
            yield session
            await session.commit()

    async def override_redis():
        yield redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_redis
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        ac.redis = redis
        yield ac
    app.dependency_overrides.clear()
    await engine.dispose()


EVENT = {
    "event": "booking.assigned",
    "recipients": [{"user_id": "cust", "role": "customer"}, {"user_id": "prov", "role": "provider"}],
    "data": {"booking_number": "BK-7", "scheduled_at": "12 Oct, 10:30", "booking_id": "b7"},
}


@pytest.mark.asyncio
async def test_services_notify_each_party_in_their_own_words(client):
    resp = await client.post("/internal/notifications/events", json=EVENT, headers={"X-Internal-Key": KEY})
    assert resp.json() == {"created": 2}

    cust = (await client.get("/api/v1/notifications/me", headers=auth("cust"))).json()["items"]
    prov = (await client.get("/api/v1/notifications/me", headers=auth("prov"))).json()["items"]
    assert [(n["title"], n["body"]) for n in cust] == [("Provider assigned", "A provider has been assigned to booking BK-7.")]
    assert [(n["title"], n["body"]) for n in prov] == [("New job", "You have been assigned booking BK-7 for 12 Oct, 10:30.")]
    assert json.loads(cust[0]["data"])["booking_id"] == "b7"
    # Open apps hear about it straight away.
    assert [c for c, _ in client.redis.published] == ["notifications:cust", "notifications:prov"]


@pytest.mark.asyncio
async def test_only_services_holding_the_key_can_notify(client, monkeypatch):
    url = "/internal/notifications/events"
    assert (await client.post(url, json=EVENT)).status_code == 401
    assert (await client.post(url, json=EVENT, headers={"X-Internal-Key": "guess"})).status_code == 401
    # A user's token is not a service key.
    assert (await client.post(url, json=EVENT, headers=auth("cust"))).status_code == 401
    # The gateway only forwards /api/v1, and nothing is served there for this.
    assert (await client.post("/api/v1/internal/notifications/events", json=EVENT, headers={"X-Internal-Key": KEY})).status_code == 404

    monkeypatch.setattr(settings, "INTERNAL_API_KEY", "")
    assert (await client.post(url, json=EVENT, headers={"X-Internal-Key": ""})).status_code == 503


@pytest.mark.asyncio
async def test_unknown_events_notify_nobody(client):
    body = {**EVENT, "event": "booking.pending"}
    assert (await client.post("/internal/notifications/events", json=body, headers={"X-Internal-Key": KEY})).json() == {"created": 0}


def test_messages_fill_in_what_is_known():
    assert render("booking.confirmed", "customer", {"booking_number": "BK-1", "scheduled_at": "12 Oct, 10:30"}) == (
        "Booking confirmed", "Your booking BK-1 for 12 Oct, 10:30 is confirmed.",
    )
    # A role without its own wording gets the general message.
    assert render("booking.cancelled", "shop", {"booking_number": "BK-1", "scheduled_at": "12 Oct"})[0] == "Booking cancelled"
    assert render("payment.completed", "shop", {"amount": "499.00"})[1] == "A customer paid ₹499.00 for a booking."
    assert render("nothing.happened", None, {}) is None


@pytest.mark.asyncio
async def test_push_uses_fcm_http_v1_with_a_service_account_token():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    calls = []

    def google(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "ya29.token", "expires_in": 3600})
        return httpx.Response(200, json={"name": "projects/alakh/messages/1"})

    fcm = FCMChannel(
        {"project_id": "alakh", "client_email": "push@alakh.iam.gserviceaccount.com", "private_key": pem,
         "token_uri": "https://oauth2.googleapis.com/token"},
        transport=httpx.MockTransport(google),
    )
    assert await fcm.send("device-1", "Hi", "There", {"booking_id": "b1", "n": 3})
    assert await fcm.send("device-2", "Hi", "Again")

    token_call, send_call, second_send = calls
    assert token_call.url.path == "/token"
    assertion = dict(x.split("=") for x in token_call.content.decode().split("&"))["assertion"]
    claims = jwt.get_unverified_claims(assertion)
    assert (claims["iss"], claims["scope"]) == ("push@alakh.iam.gserviceaccount.com", "https://www.googleapis.com/auth/firebase.messaging")
    assert send_call.url.path == "/v1/projects/alakh/messages:send"
    assert send_call.headers["authorization"] == "Bearer ya29.token"
    assert json.loads(send_call.content)["message"] == {
        "token": "device-1", "notification": {"title": "Hi", "body": "There"}, "data": {"booking_id": "b1", "n": "3"},
    }
    # The OAuth token is reused rather than fetched per message.
    assert second_send.url.path.endswith("messages:send")

    assert not await FCMChannel(None).send("device-1", "Hi", "There")
