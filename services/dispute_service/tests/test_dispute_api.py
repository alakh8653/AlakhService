"""API tests for listing disputes and moving them through review, escalation and resolution."""

import json

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models.dispute  # noqa: F401  (registers the models on Base.metadata)
from app.config import settings
from app.core.audit import AuditReporter, get_audit_reporter
from app.database import Base, get_db
from app.dependencies import Caller, booking_visible_to, get_booking_check
from app.main import app

B1, B2 = "00000000-0000-4000-8000-000000000001", "00000000-0000-4000-8000-000000000002"
# Who booking_service would show each booking to.
BOOKING_PARTIES = {B1: {"cust-1", "owner-1"}}


def auth(sub: str, role: str = "admin") -> dict:
    token = jwt.encode({"sub": sub, "role": role, "type": "access"}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session
            await session.commit()

    async def booking_check(booking_id, caller):
        return caller.user_id in BOOKING_PARTIES.get(booking_id, set())

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_booking_check] = lambda: booking_check
    # Requests are made as an admin unless a test says otherwise.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers=auth("ops")) as ac:
        yield ac
    app.dependency_overrides.clear()
    await engine.dispose()


async def create(client, booking_id=B1, raised_by="cust-1", dispute_type="service_quality"):
    resp = await client.post(
        "/api/v1/disputes",
        json={"booking_id": booking_id, "raised_by": raised_by, "dispute_type": dispute_type, "description": "Late"},
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_list_disputes_paginates_newest_first(client):
    ids = [(await create(client, booking_id=f"00000000-0000-4000-8000-00000000001{i}"))["id"] for i in range(3)]

    resp = await client.get("/api/v1/disputes", params={"page": 1, "per_page": 2})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert body["page"] == 1 and body["per_page"] == 2
    assert len(body["data"]) == 2

    page2 = (await client.get("/api/v1/disputes", params={"page": 2, "per_page": 2})).json()
    seen = {d["id"] for d in body["data"]} | {d["id"] for d in page2["data"]}
    assert seen == set(ids)


@pytest.mark.asyncio
async def test_list_disputes_filters(client):
    first = await create(client, booking_id=B1, raised_by="cust-1")
    await create(client, booking_id=B2, raised_by="cust-2")
    await client.post(f"/api/v1/disputes/{first['id']}/review")

    by_status = (await client.get("/api/v1/disputes", params={"status": "UNDER_REVIEW"})).json()
    assert [d["id"] for d in by_status["data"]] == [first["id"]]

    by_customer = (await client.get("/api/v1/disputes", params={"raised_by": "cust-2"})).json()
    assert by_customer["total"] == 1 and by_customer["data"][0]["booking_id"] == B2

    assert (await client.get("/api/v1/disputes", params={"status": "NOPE"})).status_code == 422


@pytest.mark.asyncio
async def test_review_escalate_resolve_flow(client):
    dispute = await create(client)
    base = f"/api/v1/disputes/{dispute['id']}"

    # Escalation is only allowed from review.
    assert (await client.post(f"{base}/escalate")).status_code == 400
    assert (await client.post(f"{base}/review")).json()["status"] == "UNDER_REVIEW"
    assert (await client.post(f"{base}/escalate")).json()["status"] == "ESCALATED"

    resolved = (await client.post(f"{base}/resolve", json={"resolution": "Refunded 50%"})).json()
    assert resolved["status"] == "RESOLVED"
    assert resolved["resolution"] == "Refunded 50%"
    assert resolved["resolved_at"] is not None


@pytest.mark.asyncio
async def test_only_booking_parties_raise_and_see_disputes(client):
    customer, owner, stranger = auth("cust-1", "user"), auth("owner-1", "user"), auth("stranger", "user")
    body = {"booking_id": B1, "raised_by": "someone-else", "dispute_type": "service_quality", "description": "Late"}

    assert (await client.post("/api/v1/disputes", json=body, headers={"Authorization": ""})).status_code == 401
    assert (await client.post("/api/v1/disputes", json=body, headers=stranger)).status_code == 404
    created = await client.post("/api/v1/disputes", json=body, headers=customer)
    assert created.status_code == 201
    dispute = created.json()
    assert dispute["raised_by"] == "cust-1"  # never the name the client sent

    url = f"/api/v1/disputes/{dispute['id']}"
    assert (await client.get(url, headers=stranger)).status_code == 404
    assert (await client.get(url, headers=owner)).status_code == 200  # the shop can answer

    reply = await client.post(
        f"{url}/messages", json={"author_id": "cust-1", "content": "We were on time"}, headers=owner
    )
    assert reply.status_code == 201
    assert reply.json()["author_id"] == "owner-1"
    assert (await client.get(f"{url}/messages", headers=stranger)).status_code == 404
    assert len((await client.get(f"{url}/messages", headers=customer)).json()) == 1

    # Users list only what they raised; only admins move a dispute along.
    assert [d["id"] for d in (await client.get("/api/v1/disputes", headers=owner)).json()["data"]] == []
    assert [d["id"] for d in (await client.get("/api/v1/disputes", headers=customer)).json()["data"]] == [dispute["id"]]
    assert (await client.post(f"{url}/review", headers=customer)).status_code == 403
    assert (await client.post(f"{url}/resolve", json={"resolution": "refund"}, headers=owner)).status_code == 403
    assert (await client.post(f"{url}/review")).status_code == 200


@pytest.mark.asyncio
async def test_the_app_raises_disputes_without_naming_anyone(client):
    body = {"booking_id": B1, "dispute_type": "service_quality", "description": "Arrived two hours late"}
    created = await client.post("/api/v1/disputes", json=body, headers=auth("cust-1", "user"))
    assert (created.status_code, created.json()["raised_by"]) == (201, "cust-1")
    assert (
        await client.post("/api/v1/disputes", json={**body, "description": ""}, headers=auth("cust-1", "user"))
    ).status_code == 422


def booking_service_answering(monkeypatch, handler):
    """Point the real booking check at a fake booking_service; returns the paths it was asked for."""
    seen = []

    def record(request):
        seen.append(request.url.raw_path.decode())
        return handler(request)

    real_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real_client(**kw, transport=httpx.MockTransport(record)))
    return seen


@pytest.mark.asyncio
async def test_booking_ids_cannot_steer_the_party_check_elsewhere(client, monkeypatch):
    # booking_service lists the caller's own bookings at /api/v1/bookings, which always answers 200.
    seen = booking_service_answering(
        monkeypatch, lambda req: httpx.Response(200 if req.url.path == "/api/v1/bookings" else 404)
    )
    del app.dependency_overrides[get_booking_check]
    body = {"booking_id": "../bookings", "dispute_type": "service_quality", "description": "Late"}
    resp = await client.post("/api/v1/disputes", json=body, headers=auth("stranger", "user"))
    assert resp.status_code == 422
    assert seen == []

    caller = Caller("stranger", "user", "t")
    assert await booking_visible_to("x/../../bookings", caller) is False
    assert seen == ["/api/v1/bookings/x%2F..%2F..%2Fbookings"]


def admin_service_api(reports: list, status: int = 201, fail: bool = False) -> httpx.MockTransport:
    """Stands in for admin_service's POST /internal/audit-logs."""

    def handler(request: httpx.Request) -> httpx.Response:
        if fail:
            raise httpx.ConnectError("admin_service is down")
        assert request.url.path == "/internal/audit-logs"
        reports.append((request.headers["x-internal-key"], json.loads(request.content)))
        return httpx.Response(status)

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_admin_status_changes_are_reported_to_the_audit_log(client):
    reports: list = []
    app.dependency_overrides[get_audit_reporter] = lambda: AuditReporter(
        "http://admin", "audit-key", transport=admin_service_api(reports)
    )
    dispute = await create(client)
    base = f"/api/v1/disputes/{dispute['id']}"
    origin = {"X-Real-IP": "203.0.113.4", "User-Agent": "AdminDashboard/2.0"}

    await client.post(f"{base}/review", headers=origin)
    assert (await client.post(f"{base}/escalate", headers={**origin, **auth("lead")})).status_code == 200
    await client.post(f"{base}/resolve", json={"resolution": "Refunded 50%"}, headers=origin)
    # A refused change is not reported.
    assert (await client.post(f"{base}/review", headers=origin)).status_code == 400

    assert {key for key, _ in reports} == {"audit-key"}
    entries = [entry for _, entry in reports]
    assert [(e["admin_id"], e["action"], e["old_values"], e["new_values"]) for e in entries] == [
        ("ops", "update_dispute_status", {"status": "OPEN"}, {"status": "UNDER_REVIEW"}),
        ("lead", "update_dispute_status", {"status": "UNDER_REVIEW"}, {"status": "ESCALATED"}),
        ("ops", "resolve_dispute", {"status": "ESCALATED"}, {"status": "RESOLVED", "resolution": "Refunded 50%"}),
    ]
    assert {
        (e["resource_type"], e["resource_id"], e["ip_address"], e["user_agent"], e["service"]) for e in entries
    } == {("dispute", dispute["id"], "203.0.113.4", "AdminDashboard/2.0", "dispute_service")}


@pytest.mark.asyncio
@pytest.mark.parametrize("broken", [{"status": 500}, {"fail": True}])
async def test_a_failing_admin_service_never_stops_a_resolution(client, broken):
    reports: list = []
    app.dependency_overrides[get_audit_reporter] = lambda: AuditReporter(
        "http://admin", "audit-key", transport=admin_service_api(reports, **broken)
    )
    dispute = await create(client)
    resolved = await client.post(f"/api/v1/disputes/{dispute['id']}/resolve", json={"resolution": "Refunded"})
    assert (resolved.status_code, resolved.json()["status"]) == (200, "RESOLVED")
    assert (await client.get(f"/api/v1/disputes/{dispute['id']}")).json()["status"] == "RESOLVED"


@pytest.mark.asyncio
async def test_only_admins_change_a_dispute_status(client):
    reports: list = []
    app.dependency_overrides[get_audit_reporter] = lambda: AuditReporter(
        "http://admin", "audit-key", transport=admin_service_api(reports)
    )
    dispute = await create(client)
    customer = auth("cust-1", "user")
    for action, body in (("review", None), ("escalate", None), ("resolve", {"resolution": "mine"})):
        resp = await client.post(f"/api/v1/disputes/{dispute['id']}/{action}", json=body, headers=customer)
        assert resp.status_code == 403
    assert reports == []
