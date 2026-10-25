"""GDPR requests and consent records are the user's own (or an admin's to manage)."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models.compliance  # noqa: F401  (registers the models on Base.metadata)
from app.config import settings
from app.database import Base, get_db
from app.main import app


def auth(sub: str, role: str = "user", token_type: str = "access") -> dict:
    token = jwt.encode(
        {"sub": sub, "role": role, "type": token_type}, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return {"Authorization": f"Bearer {token}"}


ALICE, BOB, ADMIN = auth("alice"), auth("bob"), auth("ops", "admin")


@pytest_asyncio.fixture
async def client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

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
async def test_users_manage_only_their_own_data(client):
    assert (await client.post("/api/v1/gdpr/export", json={"user_id": "alice"})).status_code == 401
    assert (await client.post("/api/v1/gdpr/export", json={"user_id": "bob"}, headers=ALICE)).status_code == 403
    assert (await client.post("/api/v1/gdpr/erasure", json={"user_id": "bob"}, headers=ALICE)).status_code == 403
    assert (await client.get("/api/v1/consent/bob", headers=ALICE)).status_code == 403

    export = await client.post("/api/v1/gdpr/export", json={"user_id": "alice"}, headers=ALICE)
    assert export.status_code == 201
    url = f"/api/v1/gdpr/export/{export.json()['id']}"
    assert (await client.get(url, headers=ALICE)).status_code == 200
    assert (await client.get(url, headers=BOB)).status_code == 404
    assert (await client.get(url, headers=ADMIN)).status_code == 200
    assert (await client.get("/api/v1/consent/alice", headers=ALICE)).status_code == 200


@pytest.mark.asyncio
async def test_consent_evidence_comes_from_the_request_not_the_body(client):
    body = {
        "user_id": "alice",
        "consent_type": "marketing",
        "granted": True,
        "ip_address": "6.6.6.6",
        "user_agent": "forged",
    }
    headers = {**ALICE, "X-Real-IP": "203.0.113.7", "User-Agent": "AlakhApp/2.1 (Android)"}
    record = (await client.post("/api/v1/consent", json=body, headers=headers)).json()
    assert (record["ip_address"], record["user_agent"]) == ("203.0.113.7", "AlakhApp/2.1 (Android)")

    # Without the gateway header the socket peer is recorded.
    direct = (await client.post("/api/v1/consent", json=body, headers=ALICE)).json()
    assert direct["ip_address"] == "127.0.0.1"
    assert direct["user_agent"] != "forged"


@pytest.mark.asyncio
async def test_gdpr_requests_are_visible_and_admins_close_them(client):
    export = (await client.post("/api/v1/gdpr/export", json={"user_id": "alice"}, headers=ALICE)).json()
    erasure = (await client.post("/api/v1/gdpr/erasure", json={"user_id": "alice"}, headers=ALICE)).json()
    await client.post("/api/v1/gdpr/export", json={"user_id": "bob"}, headers=BOB)

    assert [e["id"] for e in (await client.get("/api/v1/gdpr/export", headers=ALICE)).json()] == [export["id"]]
    assert [e["id"] for e in (await client.get("/api/v1/gdpr/erasure", headers=ALICE)).json()] == [erasure["id"]]
    assert (await client.get("/api/v1/gdpr/export", params={"user_id": "bob"}, headers=ALICE)).status_code == 403
    erasure_url = f"/api/v1/gdpr/erasure/{erasure['id']}"
    assert (await client.get(erasure_url, headers=ALICE)).json()["status"] == "PENDING"
    assert (await client.get(erasure_url, headers=BOB)).status_code == 404

    queue = "/api/v1/gdpr/admin/requests"
    assert (await client.get(queue, headers=ALICE)).status_code == 403
    pending = (await client.get(queue, headers=ADMIN)).json()
    assert (len(pending["exports"]), len(pending["erasures"])) == (2, 1)
    assert (await client.get(queue, params={"limit": 0}, headers=ADMIN)).status_code == 422

    export_decision = f"/api/v1/gdpr/admin/export/{export['id']}/decision"
    erasure_decision = f"/api/v1/gdpr/admin/erasure/{erasure['id']}/decision"
    assert (await client.post(export_decision, json={"status": "COMPLETED"}, headers=ALICE)).status_code == 403
    assert (await client.post(export_decision, json={"status": "COMPLETED"}, headers=ADMIN)).status_code == 422
    done = await client.post(
        export_decision, json={"status": "COMPLETED", "export_url": "https://files/alice.zip"}, headers=ADMIN
    )
    assert done.json()["status"] == "COMPLETED"
    rejected = await client.post(
        erasure_decision, json={"status": "REJECTED", "note": "Open dispute on a booking"}, headers=ADMIN
    )
    assert rejected.status_code == 200
    assert (await client.post(erasure_decision, json={"status": "COMPLETED"}, headers=ADMIN)).status_code == 409

    seen = (await client.get(erasure_url, headers=ALICE)).json()
    assert (seen["status"], seen["resolution_note"]) == ("REJECTED", "Open dispute on a booking")
    assert seen["completed_at"] is not None
    assert (await client.get(f"/api/v1/gdpr/export/{export['id']}", headers=ALICE)).json()["export_url"]
    left = (await client.get(queue, headers=ADMIN)).json()
    assert (len(left["exports"]), len(left["erasures"])) == (1, 0)
