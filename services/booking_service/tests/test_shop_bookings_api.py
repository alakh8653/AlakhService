"""Shop-scoped booking list and summary, with ownership enforced."""
import json
import os
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool, StaticPool

from app.config import settings
from app.core.notifier import get_notifier
from app.database import Base, get_db
from app.dependencies import get_service_lookup, get_shop_owner_lookup, get_staff_lookup
from app.main import app
from app.models.booking import Booking

SENT: list = []


class RecordingNotifier:
    async def send(self, event, recipients, data):
        SENT.append((event, [(r["user_id"], r["role"]) for r in recipients], data))


TEST_DB = os.environ.get("TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
OWNERS = {"shop-1": "owner-1", "shop-2": "owner-2"}
STAFF = {"shop-1": {"staff-1", "staff-2"}}  # provider accounts of each shop's active staff
LISTINGS = {
    "svc-a": {"id": "svc-a", "name": "Haircut", "shop_id": "shop-1", "price_cents": 49900, "duration_minutes": 45, "is_active": True},
    "svc-off": {"id": "svc-off", "shop_id": "shop-1", "price_cents": 100, "duration_minutes": 30, "is_active": False},
}


def auth(sub: str, role: str = "user") -> dict:
    token = jwt.encode({"sub": sub, "role": role, "type": "access"}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {"Authorization": f"Bearer {token}"}


def booking(n, shop, status, day, amount=1000, service="svc-a", customer="c1", provider=None):
    at = datetime(2026, 10, day, 10, tzinfo=timezone.utc)
    return Booking(
        id=f"bk-{n}", booking_number=f"BK-{n}", customer_id=customer, provider_id=provider, service_id=service,
        shop_id=shop, status=status, scheduled_at=at, duration_minutes=60, total_amount=amount,
        created_at=at, updated_at=at,
    )


@pytest_asyncio.fixture
async def client():
    engine = create_async_engine(TEST_DB, poolclass=StaticPool if ":memory:" in TEST_DB else NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        db.add_all([
            booking(1, "shop-1", "COMPLETED", 1, 5000, "svc-a", "c1", "staff-1"),
            booking(2, "shop-1", "COMPLETED", 1, 3000, "svc-b", "c2"),
            booking(3, "shop-1", "CANCELLED", 2, 4000, "svc-a", "c1"),
            booking(4, "shop-1", "PENDING", 3, 2000, "svc-a", "c3", "staff-1"),
            booking(5, "shop-1", "COMPLETED", 20, 9000, "svc-a", "c1"),   # outside the summary range
            booking(6, "shop-2", "COMPLETED", 1, 7000, "svc-z", "c9"),    # another shop
        ])
        await db.commit()

    async def override_get_db():
        async with factory() as session:
            yield session
            await session.commit()

    async def fake_owner(shop_id):
        return OWNERS.get(shop_id)

    app.dependency_overrides[get_db] = override_get_db
    async def fake_listing(service_id):
        return LISTINGS.get(service_id)

    app.dependency_overrides[get_shop_owner_lookup] = lambda: fake_owner
    app.dependency_overrides[get_service_lookup] = lambda: fake_listing

    async def fake_staff(shop_id, token):
        return STAFF.get(shop_id, set())

    app.dependency_overrides[get_staff_lookup] = lambda: fake_staff
    app.dependency_overrides[get_notifier] = RecordingNotifier
    SENT.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_only_the_owner_or_an_admin_sees_shop_bookings(client):
    assert (await client.get("/api/v1/bookings/shop/shop-1")).status_code in (401, 403)
    assert (await client.get("/api/v1/bookings/shop/shop-1", headers=auth("owner-2"))).status_code == 403
    assert (await client.get("/api/v1/bookings/shop/nope", headers=auth("owner-1"))).status_code == 404
    assert (await client.get("/api/v1/bookings/shop/shop-1", headers=auth("someone", "admin"))).status_code == 200


@pytest.mark.asyncio
async def test_list_filters_by_status_provider_and_date(client):
    owner = auth("owner-1")
    everything = (await client.get("/api/v1/bookings/shop/shop-1", headers=owner)).json()
    assert everything["total"] == 5
    assert everything["items"][0]["id"] == "bk-5"  # latest scheduled first
    assert all(b["shop_id"] == "shop-1" for b in everything["items"])

    completed = (await client.get("/api/v1/bookings/shop/shop-1", params={"status": "COMPLETED"}, headers=owner)).json()
    assert {b["id"] for b in completed["items"]} == {"bk-1", "bk-2", "bk-5"}

    staff = (await client.get("/api/v1/bookings/shop/shop-1", params={"provider_id": "staff-1"}, headers=owner)).json()
    assert {b["id"] for b in staff["items"]} == {"bk-1", "bk-4"}

    window = (
        await client.get("/api/v1/bookings/shop/shop-1", params={"date_from": "2026-10-02", "date_to": "2026-10-03"}, headers=owner)
    ).json()
    assert {b["id"] for b in window["items"]} == {"bk-3", "bk-4"}


@pytest.mark.asyncio
async def test_summary(client):
    resp = await client.get(
        "/api/v1/bookings/shop/shop-1/summary", params={"date_from": "2026-10-01", "date_to": "2026-10-03"}, headers=auth("owner-1")
    )
    assert resp.status_code == 200
    s = resp.json()
    assert s["total_bookings"] == 4
    assert s["total_revenue"] == 8000              # completed only: 5000 + 3000
    assert s["unique_customers"] == 3
    assert s["by_status"] == {"COMPLETED": 2, "CANCELLED": 1, "PENDING": 1}
    assert s["by_day"] == [
        {"day": "2026-10-01", "revenue": 8000, "bookings": 2},
        {"day": "2026-10-02", "revenue": 0, "bookings": 1},
        {"day": "2026-10-03", "revenue": 0, "bookings": 1},
    ]
    assert s["top_services"][0] == {"service_id": "svc-a", "bookings": 3, "revenue": 5000}

    bad = await client.get(
        "/api/v1/bookings/shop/shop-1/summary", params={"date_from": "2026-10-05", "date_to": "2026-10-01"}, headers=auth("owner-1")
    )
    assert bad.status_code == 400


@pytest.mark.asyncio
async def test_status_change_and_cancel_endpoints_return_the_booking(client):
    owner = auth("owner-1")
    confirmed = await client.put("/api/v1/bookings/bk-4/status", json={"status": "CONFIRMED"}, headers=owner)
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "CONFIRMED"

    cancelled = await client.post("/api/v1/bookings/bk-4/cancel", json={"reason": "Shop closed"}, headers=owner)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"

    rejected = await client.post("/api/v1/bookings/bk-1/cancel", json={"reason": "Too late"}, headers=owner)
    assert rejected.status_code == 400


@pytest.mark.asyncio
async def test_strangers_cannot_see_or_change_a_booking(client):
    stranger = auth("stranger")
    assert (await client.get("/api/v1/bookings/bk-4", headers=stranger)).status_code == 404
    assert (await client.get("/api/v1/bookings/bk-4/history", headers=stranger)).status_code == 404
    assert (await client.put("/api/v1/bookings/bk-4/status", json={"status": "CONFIRMED"}, headers=stranger)).status_code == 404
    assert (await client.post("/api/v1/bookings/bk-4/cancel", json={"reason": "x"}, headers=stranger)).status_code == 404
    # Owning a different shop does not help.
    assert (await client.put("/api/v1/bookings/bk-4/status", json={"status": "CONFIRMED"}, headers=auth("owner-2"))).status_code == 404


@pytest.mark.asyncio
async def test_each_party_may_only_make_its_own_transitions(client):
    customer, provider = auth("c3"), auth("staff-1")  # bk-4: PENDING, customer c3, provider staff-1, shop-1

    assert (await client.get("/api/v1/bookings/bk-4", headers=customer)).status_code == 200
    assert (await client.get("/api/v1/bookings/bk-4", headers=provider)).status_code == 200

    # Confirming is the shop's call, not the customer's or the provider's.
    assert (await client.put("/api/v1/bookings/bk-4/status", json={"status": "CONFIRMED"}, headers=customer)).status_code == 403
    assert (await client.put("/api/v1/bookings/bk-4/status", json={"status": "CONFIRMED"}, headers=provider)).status_code == 403
    assert (await client.post("/api/v1/bookings/bk-4/cancel", json={"reason": "x"}, headers=provider)).status_code == 403

    # The customer may cancel their own booking.
    cancelled = await client.post("/api/v1/bookings/bk-4/cancel", json={"reason": "Changed plans"}, headers=customer)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"


@pytest.mark.asyncio
async def test_admin_may_resolve_what_others_cannot(client):
    # bk-1 is COMPLETED; disputing is the customer's call, refunding the admin's.
    assert (await client.put("/api/v1/bookings/bk-1/status", json={"status": "DISPUTED"}, headers=auth("c1"))).status_code == 200
    assert (await client.put("/api/v1/bookings/bk-1/status", json={"status": "REFUNDED"}, headers=auth("owner-1"))).status_code == 403
    refunded = await client.put("/api/v1/bookings/bk-1/status", json={"status": "REFUNDED"}, headers=auth("ops", "admin"))
    assert refunded.status_code == 200
    assert refunded.json()["status"] == "REFUNDED"


@pytest.mark.asyncio
async def test_only_access_tokens_authenticate(client):
    for claims in ({"sub": "owner-1", "type": "refresh"}, {"sub": "owner-1", "type": "access", "purpose": "password_reset"}):
        token = jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        resp = await client.get("/api/v1/bookings/shop/shop-1", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_bookings_are_priced_from_the_catalogue(client):
    body = {
        "customer_id": "someone-else",
        "service_id": "svc-a",
        "shop_id": "shop-2",
        "scheduled_at": "2026-11-01T10:00:00Z",
        "duration_minutes": 5,
        "total_amount": 1,
    }
    created = await client.post("/api/v1/bookings", json=body, headers=auth("c7"))
    assert created.status_code == 201
    booking = created.json()
    assert booking["total_amount"] == 49900
    assert booking["shop_id"] == "shop-1"
    assert booking["duration_minutes"] == 45
    assert booking["customer_id"] == "c7"

    assert (await client.post("/api/v1/bookings", json={**body, "service_id": "nope"}, headers=auth("c7"))).status_code == 404
    assert (await client.post("/api/v1/bookings", json={**body, "service_id": "svc-off"}, headers=auth("c7"))).status_code == 409


@pytest.mark.asyncio
async def test_who_may_track_a_provider(client):
    url = "/api/v1/bookings/tracking/staff-1"

    async def allowed(headers):
        return (await client.get(url, headers=headers)).status_code == 200

    # bk-4 (PENDING, customer c3, shop-1) is not active yet, so no one but the provider and admins.
    assert await allowed(auth("staff-1"))
    assert await allowed(auth("ops", "admin"))
    assert not await allowed(auth("c3"))
    assert not await allowed(auth("owner-1"))

    owner = auth("owner-1")
    assert (await client.put("/api/v1/bookings/bk-4/status", json={"status": "CONFIRMED"}, headers=owner)).status_code == 200
    assert (await client.post("/api/v1/bookings/bk-4/assign", json={"provider_id": "staff-1"}, headers=owner)).status_code == 200
    assert await allowed(auth("c3"))  # its customer, while the job is under way
    assert await allowed(owner)  # and the shop running it
    assert not await allowed(auth("c1"))  # another of the provider's customers, finished earlier
    assert not await allowed(auth("owner-2"))
    assert (await client.get(url)).status_code in (401, 403)


@pytest.mark.asyncio
async def test_assigning_a_provider(client):
    owner, url = auth("owner-1"), "/api/v1/bookings/bk-4/assign"
    await client.put("/api/v1/bookings/bk-4/status", json={"status": "CONFIRMED"}, headers=owner)

    # ASSIGNED is never set without a provider.
    assert (await client.put("/api/v1/bookings/bk-4/status", json={"status": "ASSIGNED"}, headers=owner)).status_code == 400
    assert (await client.post(url, json={"provider_id": "staff-2"}, headers=auth("c3"))).status_code == 403  # the customer
    assert (await client.post(url, json={"provider_id": "staff-2"}, headers=auth("owner-2"))).status_code == 404  # another shop
    assert (await client.post(url, json={"provider_id": "outsider"}, headers=owner)).status_code == 422  # not shop staff

    assigned = await client.post(url, json={"provider_id": "staff-2"}, headers=owner)
    assert assigned.status_code == 200
    assert assigned.json()["status"] == "ASSIGNED" and assigned.json()["provider_id"] == "staff-2"
    history = (await client.get("/api/v1/bookings/bk-4/history", headers=owner)).json()
    assert history[-1]["to_status"] == "ASSIGNED" and history[-1]["changed_by"] == "owner-1"

    # The assigned provider now runs the job; assigning again is not a valid transition.
    assert (await client.put("/api/v1/bookings/bk-4/status", json={"status": "PROVIDER_EN_ROUTE"}, headers=auth("staff-2"))).status_code == 200
    assert (await client.post(url, json={"provider_id": "staff-1"}, headers=owner)).status_code == 400


@pytest.mark.asyncio
async def test_admins_and_dispatch_can_assign_anyone(client):
    admin = auth("dispatch", "admin")
    await client.put("/api/v1/bookings/bk-4/status", json={"status": "CONFIRMED"}, headers=admin)
    assigned = await client.post("/api/v1/bookings/bk-4/assign", json={"provider_id": "freelancer-9"}, headers=admin)
    assert assigned.status_code == 200 and assigned.json()["provider_id"] == "freelancer-9"


@pytest.mark.asyncio
async def test_everyone_on_a_booking_hears_about_changes_made_by_someone_else(client):
    created = await client.post(
        "/api/v1/bookings", json={"service_id": "svc-a", "scheduled_at": "2026-10-12T05:00:00Z"}, headers=auth("c1"),
    )
    assert created.status_code == 201
    event, recipients, data = SENT[-1]
    # The shop hears about a new booking; the customer who made it does not.
    assert (event, recipients) == ("booking.created", [("owner-1", "shop")])
    assert (data["service_name"], data["booking_number"]) == ("Haircut", created.json()["booking_number"])
    assert data["scheduled_at"] == "12 Oct, 10:30 AM"  # shown in India time

    await client.put("/api/v1/bookings/bk-4/status", json={"status": "CONFIRMED"}, headers=auth("owner-1"))
    assert SENT[-1][:2] == ("booking.confirmed", [("c3", "customer"), ("staff-1", "provider")])

    await client.post("/api/v1/bookings/bk-4/cancel", json={"reason": "Plans changed"}, headers=auth("c3"))
    assert SENT[-1][:2] == ("booking.cancelled", [("staff-1", "provider"), ("owner-1", "shop")])

    # Refused changes notify nobody.
    count = len(SENT)
    await client.put("/api/v1/bookings/bk-4/status", json={"status": "COMPLETED"}, headers=auth("c3"))
    assert len(SENT) == count


@pytest.mark.asyncio
async def test_notifier_posts_to_notification_service_with_the_internal_key():
    import httpx

    from app.core.notifier import Notifier

    seen = []

    def service(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"created": 1})

    notifier = Notifier("http://notification_service:8000", "k3y", transport=httpx.MockTransport(service))
    await notifier.send("booking.confirmed", [{"user_id": "c1", "role": "customer"}], {"booking_number": "BK-1"})
    assert seen[0].url.path == "/internal/notifications/events"
    assert seen[0].headers["x-internal-key"] == "k3y"
    assert json.loads(seen[0].content)["recipients"] == [{"user_id": "c1", "role": "customer"}]

    def down(request):
        raise httpx.ConnectError("refused")

    # Delivery problems never surface to the caller.
    await Notifier("http://nowhere", "k3y", transport=httpx.MockTransport(down)).send("booking.confirmed", [{"user_id": "c1"}], {})
    # Without a key nothing is sent at all.
    await Notifier("http://notification_service:8000", "", transport=httpx.MockTransport(service)).send("x", [{"user_id": "c1"}], {})
    assert len(seen) == 1
