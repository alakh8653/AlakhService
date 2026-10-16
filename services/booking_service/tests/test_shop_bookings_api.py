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
from app.dependencies import (
    CouponRejected,
    get_coupon_pricer,
    get_service_lookup,
    get_shop_owner_lookup,
    get_staff_lookup,
)
from app.main import app
from app.models.booking import Booking

SENT: list = []
PRICED: list = []


async def fake_pricer(token, customer_id, service_id, list_price, code):
    """Stands in for pricing_engine: WELCOME10 takes 10% off, once per customer."""
    if code != "WELCOME10":
        raise CouponRejected("Coupon not found")
    if (customer_id, code) in [(c, k) for c, _, k in PRICED]:
        raise CouponRejected("Coupon already used")
    PRICED.append((customer_id, list_price, code))
    return int(list_price * 0.9)


SESSIONS: dict = {}


class RecordingNotifier:
    async def send(self, event, recipients, data):
        # By the time anyone is told, the change must be committed and visible to other requests.
        async with SESSIONS["factory"]() as db:
            stored = await db.get(Booking, data["booking_id"])
        assert stored is not None
        assert event == "booking.created" or f"booking.{stored.status.lower()}" == event
        SENT.append((event, [(r["user_id"], r["role"]) for r in recipients], data))


TEST_DB = os.environ.get("TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
OWNERS = {"shop-1": "owner-1", "shop-2": "owner-2"}
STAFF = {"shop-1": {"staff-1", "staff-2"}}  # provider accounts of each shop's active staff
LISTINGS = {
    "svc-a": {
        "id": "svc-a",
        "name": "Haircut",
        "shop_id": "shop-1",
        "price_cents": 49900,
        "duration_minutes": 45,
        "is_active": True,
    },
    "svc-off": {"id": "svc-off", "shop_id": "shop-1", "price_cents": 100, "duration_minutes": 30, "is_active": False},
    # A repair the shop can do while you wait or by collecting the item from home.
    "svc-repair": {
        "id": "svc-repair",
        "name": "Laptop screen repair",
        "shop_id": "shop-1",
        "price_cents": 450000,
        "duration_minutes": 120,
        "is_active": True,
        "service_modes": ["AT_SHOP", "PICKUP_DROP"],
        "pickup_fee_cents": 9900,
    },
    # A haircut also offered at the customer's home, for a visit fee.
    "svc-home": {
        "id": "svc-home",
        "name": "Haircut at home",
        "shop_id": "shop-1",
        "price_cents": 50000,
        "duration_minutes": 45,
        "is_active": True,
        "service_modes": ["AT_SHOP", "AT_HOME"],
        "home_visit_fee_cents": 15000,
    },
}


def auth(sub: str, role: str = "user") -> dict:
    token = jwt.encode({"sub": sub, "role": role, "type": "access"}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {"Authorization": f"Bearer {token}"}


def booking(n, shop, status, day, amount=1000, service="svc-a", customer="c1", provider=None):
    at = datetime(2026, 10, day, 10, tzinfo=timezone.utc)
    return Booking(
        id=f"bk-{n}",
        booking_number=f"BK-{n}",
        customer_id=customer,
        provider_id=provider,
        service_id=service,
        shop_id=shop,
        status=status,
        scheduled_at=at,
        duration_minutes=60,
        total_amount=amount,
        created_at=at,
        updated_at=at,
    )


@pytest_asyncio.fixture
async def client():
    engine = create_async_engine(TEST_DB, poolclass=StaticPool if ":memory:" in TEST_DB else NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        db.add_all(
            [
                booking(1, "shop-1", "COMPLETED", 1, 5000, "svc-a", "c1", "staff-1"),
                booking(2, "shop-1", "COMPLETED", 1, 3000, "svc-b", "c2"),
                booking(3, "shop-1", "CANCELLED", 2, 4000, "svc-a", "c1"),
                booking(4, "shop-1", "PENDING", 3, 2000, "svc-a", "c3", "staff-1"),
                booking(5, "shop-1", "COMPLETED", 20, 9000, "svc-a", "c1"),  # outside the summary range
                booking(6, "shop-2", "COMPLETED", 1, 7000, "svc-z", "c9"),  # another shop
            ]
        )
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
    app.dependency_overrides[get_coupon_pricer] = lambda: fake_pricer
    PRICED.clear()
    SESSIONS["factory"] = factory
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
        await client.get(
            "/api/v1/bookings/shop/shop-1", params={"date_from": "2026-10-02", "date_to": "2026-10-03"}, headers=owner
        )
    ).json()
    assert {b["id"] for b in window["items"]} == {"bk-3", "bk-4"}


@pytest.mark.asyncio
async def test_summary(client):
    resp = await client.get(
        "/api/v1/bookings/shop/shop-1/summary",
        params={"date_from": "2026-10-01", "date_to": "2026-10-03"},
        headers=auth("owner-1"),
    )
    assert resp.status_code == 200
    s = resp.json()
    assert s["total_bookings"] == 4
    assert s["total_revenue"] == 8000  # completed only: 5000 + 3000
    assert s["unique_customers"] == 3
    assert s["by_status"] == {"COMPLETED": 2, "CANCELLED": 1, "PENDING": 1}
    assert s["by_day"] == [
        {"day": "2026-10-01", "revenue": 8000, "bookings": 2},
        {"day": "2026-10-02", "revenue": 0, "bookings": 1},
        {"day": "2026-10-03", "revenue": 0, "bookings": 1},
    ]
    assert s["top_services"][0] == {"service_id": "svc-a", "bookings": 3, "revenue": 5000}

    bad = await client.get(
        "/api/v1/bookings/shop/shop-1/summary",
        params={"date_from": "2026-10-05", "date_to": "2026-10-01"},
        headers=auth("owner-1"),
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
    assert (
        await client.put("/api/v1/bookings/bk-4/status", json={"status": "CONFIRMED"}, headers=stranger)
    ).status_code == 404
    assert (
        await client.post("/api/v1/bookings/bk-4/cancel", json={"reason": "x"}, headers=stranger)
    ).status_code == 404
    # Owning a different shop does not help.
    assert (
        await client.put("/api/v1/bookings/bk-4/status", json={"status": "CONFIRMED"}, headers=auth("owner-2"))
    ).status_code == 404


@pytest.mark.asyncio
async def test_each_party_may_only_make_its_own_transitions(client):
    customer, provider = auth("c3"), auth("staff-1")  # bk-4: PENDING, customer c3, provider staff-1, shop-1

    assert (await client.get("/api/v1/bookings/bk-4", headers=customer)).status_code == 200
    assert (await client.get("/api/v1/bookings/bk-4", headers=provider)).status_code == 200

    # Confirming is the shop's call, not the customer's or the provider's.
    assert (
        await client.put("/api/v1/bookings/bk-4/status", json={"status": "CONFIRMED"}, headers=customer)
    ).status_code == 403
    assert (
        await client.put("/api/v1/bookings/bk-4/status", json={"status": "CONFIRMED"}, headers=provider)
    ).status_code == 403
    assert (
        await client.post("/api/v1/bookings/bk-4/cancel", json={"reason": "x"}, headers=provider)
    ).status_code == 403

    # The customer may cancel their own booking.
    cancelled = await client.post("/api/v1/bookings/bk-4/cancel", json={"reason": "Changed plans"}, headers=customer)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"


@pytest.mark.asyncio
async def test_admin_may_resolve_what_others_cannot(client):
    # bk-1 is COMPLETED; disputing is the customer's call, refunding the admin's.
    assert (
        await client.put("/api/v1/bookings/bk-1/status", json={"status": "DISPUTED"}, headers=auth("c1"))
    ).status_code == 200
    assert (
        await client.put("/api/v1/bookings/bk-1/status", json={"status": "REFUNDED"}, headers=auth("owner-1"))
    ).status_code == 403
    refunded = await client.put(
        "/api/v1/bookings/bk-1/status", json={"status": "REFUNDED"}, headers=auth("ops", "admin")
    )
    assert refunded.status_code == 200
    assert refunded.json()["status"] == "REFUNDED"


@pytest.mark.asyncio
async def test_only_access_tokens_authenticate(client):
    for claims in (
        {"sub": "owner-1", "type": "refresh"},
        {"sub": "owner-1", "type": "access", "purpose": "password_reset"},
    ):
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

    assert (
        await client.post("/api/v1/bookings", json={**body, "service_id": "nope"}, headers=auth("c7"))
    ).status_code == 404
    assert (
        await client.post("/api/v1/bookings", json={**body, "service_id": "svc-off"}, headers=auth("c7"))
    ).status_code == 409


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
    assert (
        await client.put("/api/v1/bookings/bk-4/status", json={"status": "CONFIRMED"}, headers=owner)
    ).status_code == 200
    assert (
        await client.post("/api/v1/bookings/bk-4/assign", json={"provider_id": "staff-1"}, headers=owner)
    ).status_code == 200
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
    assert (
        await client.put("/api/v1/bookings/bk-4/status", json={"status": "ASSIGNED"}, headers=owner)
    ).status_code == 400
    assert (
        await client.post(url, json={"provider_id": "staff-2"}, headers=auth("c3"))
    ).status_code == 403  # the customer
    assert (
        await client.post(url, json={"provider_id": "staff-2"}, headers=auth("owner-2"))
    ).status_code == 404  # another shop
    assert (
        await client.post(url, json={"provider_id": "outsider"}, headers=owner)
    ).status_code == 422  # not shop staff

    assigned = await client.post(url, json={"provider_id": "staff-2"}, headers=owner)
    assert assigned.status_code == 200
    assert assigned.json()["status"] == "ASSIGNED" and assigned.json()["provider_id"] == "staff-2"
    history = (await client.get("/api/v1/bookings/bk-4/history", headers=owner)).json()
    assert history[-1]["to_status"] == "ASSIGNED" and history[-1]["changed_by"] == "owner-1"

    # The assigned provider now runs the job; assigning again is not a valid transition.
    assert (
        await client.put("/api/v1/bookings/bk-4/status", json={"status": "PROVIDER_EN_ROUTE"}, headers=auth("staff-2"))
    ).status_code == 200
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
        "/api/v1/bookings",
        json={"service_id": "svc-a", "scheduled_at": "2026-10-12T05:00:00Z"},
        headers=auth("c1"),
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
    await Notifier("http://nowhere", "k3y", transport=httpx.MockTransport(down)).send(
        "booking.confirmed", [{"user_id": "c1"}], {}
    )
    # Without a key nothing is sent at all.
    await Notifier("http://notification_service:8000", "", transport=httpx.MockTransport(service)).send(
        "x", [{"user_id": "c1"}], {}
    )
    assert len(seen) == 1


@pytest.mark.asyncio
async def test_providers_list_the_jobs_assigned_to_them(client):
    jobs = (await client.get("/api/v1/bookings/assigned", headers=auth("staff-1"))).json()
    assert sorted(b["id"] for b in jobs["items"]) == ["bk-1", "bk-4"]
    pending = (
        await client.get("/api/v1/bookings/assigned", params={"status": "PENDING"}, headers=auth("staff-1"))
    ).json()
    assert [b["id"] for b in pending["items"]] == ["bk-4"]
    # Customers' own lists are unchanged, and nobody else's jobs show up.
    assert (await client.get("/api/v1/bookings/assigned", headers=auth("c1"))).json()["items"] == []
    assert "bk-4" not in [
        b["id"] for b in (await client.get("/api/v1/bookings", headers=auth("staff-1"))).json()["items"]
    ]

    # The provider moves their job along; the customer and shop hear about it.
    await client.put("/api/v1/bookings/bk-4/status", json={"status": "CONFIRMED"}, headers=auth("owner-1"))
    await client.post("/api/v1/bookings/bk-4/assign", json={"provider_id": "staff-1"}, headers=auth("owner-1"))
    for status in ("PROVIDER_EN_ROUTE", "IN_PROGRESS", "COMPLETED"):
        resp = await client.put("/api/v1/bookings/bk-4/status", json={"status": status}, headers=auth("staff-1"))
        assert resp.json()["status"] == status
        assert SENT[-1][:2] == (f"booking.{status.lower()}", [("c3", "customer"), ("owner-1", "shop")])


@pytest.mark.asyncio
async def test_a_coupon_discounts_the_catalogue_price_once(client):
    body = {"service_id": "svc-a", "scheduled_at": "2026-10-12T05:00:00Z"}
    plain = (await client.post("/api/v1/bookings", json=body, headers=auth("c1"))).json()
    assert (plain["total_amount"], plain["coupon_code"], plain["list_price"]) == (49900, None, 49900)

    discounted = await client.post("/api/v1/bookings", json={**body, "coupon_code": " welcome10 "}, headers=auth("c1"))
    assert discounted.status_code == 201
    assert (discounted.json()["total_amount"], discounted.json()["coupon_code"], discounted.json()["list_price"]) == (
        44910,
        "WELCOME10",
        49900,
    )
    # Priced from the catalogue, not from anything the client sent.
    assert PRICED == [("c1", 49900, "WELCOME10")]

    again = await client.post("/api/v1/bookings", json={**body, "coupon_code": "WELCOME10"}, headers=auth("c1"))
    assert (again.status_code, again.json()["detail"]) == (422, "Coupon already used")
    bogus = await client.post(
        "/api/v1/bookings", json={**body, "coupon_code": "FREE100", "total_amount": 1}, headers=auth("c2")
    )
    assert (bogus.status_code, bogus.json()["detail"]) == (422, "Coupon not found")


def new_booking(service, **extra):
    return {"service_id": service, "scheduled_at": "2026-11-01T10:00:00Z", **extra}


async def book(client, service, who="c7", **extra):
    resp = await client.post("/api/v1/bookings", json=new_booking(service, **extra), headers=auth(who))
    assert resp.status_code == 201, resp.text
    return resp.json()


async def set_status(client, booking_id, status, who):
    return await client.put(f"/api/v1/bookings/{booking_id}/status", json={"status": status}, headers=auth(who))


@pytest.mark.asyncio
async def test_customers_choose_how_the_service_is_delivered(client):
    post = lambda body: client.post("/api/v1/bookings", json=body, headers=auth("c7"))  # noqa: E731
    # A listing without modes is at the shop only.
    assert (await post(new_booking("svc-a", service_mode="AT_HOME", address_id="addr-1"))).status_code == 422
    assert (await post(new_booking("svc-repair", service_mode="AT_HOME", address_id="addr-1"))).status_code == 422
    assert (await post(new_booking("svc-a", service_mode="BY_DRONE"))).status_code == 422
    # Coming to the customer needs to know where.
    missing = await post(new_booking("svc-repair", service_mode="PICKUP_DROP"))
    assert missing.status_code == 422 and "address" in missing.json()["detail"]

    repair = await book(
        client,
        "svc-repair",
        service_mode="PICKUP_DROP",
        address_id="addr-1",
        item_description="Dell XPS 13, cracked screen",
    )
    assert (repair["service_mode"], repair["item_description"]) == ("PICKUP_DROP", "Dell XPS 13, cracked screen")
    assert (repair["total_amount"], repair["service_mode_fee"]) == (450000 + 9900, 9900)

    at_shop = await book(client, "svc-repair")
    assert (at_shop["service_mode"], at_shop["total_amount"], at_shop["service_mode_fee"]) == ("AT_SHOP", 450000, 0)

    # A coupon discounts the service; the visit fee is added on top.
    home = await book(client, "svc-home", service_mode="AT_HOME", address_id="addr-1", coupon_code="WELCOME10")
    assert home["total_amount"] == 45000 + 15000
    assert (home["list_price"], home["service_mode_fee"], home["coupon_code"]) == (65000, 15000, "WELCOME10")


@pytest.mark.asyncio
async def test_pickup_and_drop_collects_the_item_and_brings_it_back(client):
    job = await book(client, "svc-repair", service_mode="PICKUP_DROP", address_id="addr-1")
    owner = "owner-1"
    assert (await set_status(client, job["id"], "CONFIRMED", owner)).status_code == 200
    assert (
        await client.post(f"/api/v1/bookings/{job['id']}/assign", json={"provider_id": "staff-1"}, headers=auth(owner))
    ).status_code == 200

    # Work cannot start before the item is collected, nor finish before it is returned.
    started = await set_status(client, job["id"], "IN_PROGRESS", "staff-1")
    assert started.status_code == 400 and "Pick up" in started.json()["detail"]
    assert (await set_status(client, job["id"], "PROVIDER_EN_ROUTE", "staff-1")).status_code == 200
    assert (await set_status(client, job["id"], "PICKED_UP", "staff-1")).status_code == 200
    assert (await set_status(client, job["id"], "IN_PROGRESS", owner)).status_code == 200  # at the shop
    early = await set_status(client, job["id"], "COMPLETED", owner)
    assert early.status_code == 400 and "Deliver" in early.json()["detail"]
    assert (await set_status(client, job["id"], "OUT_FOR_DELIVERY", "staff-1")).status_code == 200
    assert (await set_status(client, job["id"], "COMPLETED", "staff-1")).status_code == 200

    history = (await client.get(f"/api/v1/bookings/{job['id']}/history", headers=auth(owner))).json()
    assert [h["to_status"] for h in history] == [
        "PENDING",
        "CONFIRMED",
        "ASSIGNED",
        "PROVIDER_EN_ROUTE",
        "PICKED_UP",
        "IN_PROGRESS",
        "OUT_FOR_DELIVERY",
        "COMPLETED",
    ]
    told = [
        (event, recipients)
        for event, recipients, _ in SENT
        if event in ("booking.picked_up", "booking.out_for_delivery")
    ]
    # Everyone on the booking but the person who made the change hears about it.
    both = [("c7", "customer"), ("owner-1", "shop")]
    assert told == [("booking.picked_up", both), ("booking.out_for_delivery", both)]
    # The customer cannot mark their own item delivered.
    other = await book(client, "svc-repair", service_mode="PICKUP_DROP", address_id="addr-1")
    assert (await set_status(client, other["id"], "PICKED_UP", "c7")).status_code == 403


@pytest.mark.asyncio
async def test_at_the_shop_the_service_starts_when_the_customer_arrives(client):
    walk_in = await book(client, "svc-home")
    assert (await set_status(client, walk_in["id"], "CONFIRMED", "owner-1")).status_code == 200
    # No provider travels, so the shop starts it straight from confirmed...
    assert (await set_status(client, walk_in["id"], "IN_PROGRESS", "owner-1")).status_code == 200
    assert (await set_status(client, walk_in["id"], "COMPLETED", "owner-1")).status_code == 200
    # ...and pickup steps make no sense for it.
    second = await book(client, "svc-home")
    await set_status(client, second["id"], "CONFIRMED", "owner-1")
    assert (await set_status(client, second["id"], "OUT_FOR_DELIVERY", "owner-1")).status_code == 400

    # A home visit needs a provider assigned before it can start.
    visit = await book(client, "svc-home", service_mode="AT_HOME", address_id="addr-1")
    await set_status(client, visit["id"], "CONFIRMED", "owner-1")
    refused = await set_status(client, visit["id"], "IN_PROGRESS", "owner-1")
    assert refused.status_code == 400 and "Assign a provider" in refused.json()["detail"]
