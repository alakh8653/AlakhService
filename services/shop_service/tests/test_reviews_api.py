"""Reviews shown to customers: who may write them, what the public sees, replies, reports, moderation."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models.shop  # noqa: F401
from app.config import settings
from app.database import Base, get_db
from app.dependencies import get_booking_lookup, get_name_lookup, public_name
from app.main import app


def auth(sub: str, role: str = "user") -> dict:
    token = jwt.encode({"sub": sub, "role": role, "type": "access"}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {"Authorization": f"Bearer {token}"}


OWNER = auth("owner-1")
ADMIN = auth("ops", "admin")
NAMES = {"cust-1": "Priya Sharma", "cust-2": "rahul", "cust-3": "Anita Ravi Desai"}
BOOKINGS: dict = {}


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

    async def fake_booking(booking_id, caller):
        booking = BOOKINGS.get(booking_id)
        return booking if booking and caller.user_id == booking["customer_id"] else None

    async def fake_name(caller):
        return public_name(NAMES.get(caller.user_id))

    BOOKINGS.clear()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_booking_lookup] = lambda: fake_booking
    app.dependency_overrides[get_name_lookup] = lambda: fake_name
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
    await engine.dispose()


async def make_shop(client, owner="owner-1"):
    resp = await client.post(
        "/api/v1/shops", json={"owner_id": owner, "name": f"Shop {owner}", "category": "salon"}, headers=auth(owner)
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def review(client, shop_id, customer, rating, comment=None, service_id="svc-cut", status="COMPLETED"):
    booking_id = f"bk-{len(BOOKINGS)}"
    BOOKINGS[booking_id] = {
        "id": booking_id,
        "customer_id": customer,
        "shop_id": shop_id,
        "service_id": service_id,
        "status": status,
    }
    body = {"booking_id": booking_id, "rating": rating}
    if comment is not None:
        body["comment"] = comment
    return await client.post(f"/api/v1/shops/{shop_id}/rating", json=body, headers=auth(customer))


async def reviews(client, shop_id, **params):
    resp = await client.get(f"/api/v1/shops/{shop_id}/reviews", params=params)
    assert resp.status_code == 200
    return resp.json()


def test_public_names_show_first_name_and_last_initial_only():
    assert public_name("priya ravi sharma") == "Priya S."
    assert public_name("Rahul") == "Rahul"
    assert public_name("  ") is None
    assert public_name(None) is None
    # A name field holding a contact detail is never shown.
    assert public_name("priya@example.com") is None
    assert public_name("Priya 9876543210") is None


@pytest.mark.asyncio
async def test_only_a_completed_booking_writes_a_review_once(client):
    shop = await make_shop(client)
    assert (await review(client, shop, "cust-1", 5, status="IN_PROGRESS")).status_code == 409
    for bad in (0, 6, 4.5):
        assert (await review(client, shop, "cust-1", bad)).status_code == 422
    assert (await review(client, shop, "cust-1", 4, comment="x" * 1001)).status_code == 422

    ok = await review(client, shop, "cust-1", 4.0, comment="  Neat haircut, on time.  ")
    assert ok.status_code == 200
    assert (ok.json()["average_rating"], ok.json()["review_count"]) == (4.0, 1)
    # The same booking can't be reviewed twice.
    booking_id = next(iter(BOOKINGS))
    again = await client.post(
        f"/api/v1/shops/{shop}/rating", json={"booking_id": booking_id, "rating": 1}, headers=auth("cust-1")
    )
    assert again.status_code == 409

    [item] = (await reviews(client, shop))["items"]
    assert item["comment"] == "Neat haircut, on time."
    assert item["service_id"] == "svc-cut"
    assert item["reviewer_name"] == "Priya S."
    assert item["reply"] is None
    # Nothing that identifies or contacts the customer leaves the service.
    assert not {"customer_id", "booking_id", "email", "phone"} & set(item)


@pytest.mark.asyncio
async def test_summary_list_filters_and_shop_responses(client):
    shop = await make_shop(client)
    await review(client, shop, "cust-1", 5, "Excellent")
    await review(client, shop, "cust-2", 4, service_id="svc-spa")
    await review(client, shop, "cust-3", 5, "Loved it", service_id="svc-spa")
    await review(client, shop, "cust-1", 1, "Late by an hour")

    summary = (await client.get(f"/api/v1/shops/{shop}/reviews/summary")).json()
    assert summary["average_rating"] == 3.8 and summary["review_count"] == 4
    assert summary["distribution"] == [
        {"stars": 5, "count": 2},
        {"stars": 4, "count": 1},
        {"stars": 3, "count": 0},
        {"stars": 2, "count": 0},
        {"stars": 1, "count": 1},
    ]
    spa = (await client.get(f"/api/v1/shops/{shop}/reviews/summary", params={"service_id": "svc-spa"})).json()
    assert (spa["average_rating"], spa["review_count"]) == (4.5, 2)

    page = await reviews(client, shop)
    assert page["total"] == 4
    # Newest first; a single-word name stays as it is.
    assert [i["comment"] for i in page["items"]] == ["Late by an hour", "Loved it", None, "Excellent"]
    assert page["items"][2]["reviewer_name"] == "Rahul"
    assert page["items"][1]["reviewer_name"] == "Anita D."
    assert [i["rating"] for i in (await reviews(client, shop, rating=5))["items"]] == [5, 5]
    assert (await reviews(client, shop, service_id="svc-spa"))["total"] == 2
    paged = await reviews(client, shop, skip=1, limit=2)
    assert [i["comment"] for i in paged["items"]] == ["Loved it", None] and paged["total"] == 4
    for params in ({"rating": 6}, {"limit": 0}, {"limit": 51}, {"skip": -1}):
        assert (await client.get(f"/api/v1/shops/{shop}/reviews", params=params)).status_code == 422

    # Shop detail and lists carry the rating so cards need no extra call.
    detail = (await client.get(f"/api/v1/shops/{shop}")).json()
    assert (detail["average_rating"], detail["review_count"]) == (3.8, 4)
    listed = (await client.get("/api/v1/shops")).json()
    assert (listed[0]["average_rating"], listed[0]["review_count"]) == (3.8, 4)

    other = await make_shop(client, owner="owner-2")
    briefs = (await client.get("/api/v1/shops/ratings", params={"ids": f"{other},{shop},missing,{shop}"})).json()
    assert briefs == [
        {"shop_id": other, "average_rating": 0.0, "review_count": 0},
        {"shop_id": shop, "average_rating": 3.8, "review_count": 4},
    ]
    too_many = ",".join(f"s{n}" for n in range(51))
    assert (await client.get("/api/v1/shops/ratings", params={"ids": too_many})).status_code == 422

    assert (await client.get("/api/v1/shops/nope/reviews")).status_code == 404
    assert (await client.get("/api/v1/shops/nope/reviews/summary")).status_code == 404


@pytest.mark.asyncio
async def test_a_new_shop_has_an_empty_summary(client):
    shop = await make_shop(client)
    summary = (await client.get(f"/api/v1/shops/{shop}/reviews/summary")).json()
    assert summary["average_rating"] == 0.0 and summary["review_count"] == 0
    assert [d["count"] for d in summary["distribution"]] == [0, 0, 0, 0, 0]
    assert (await reviews(client, shop)) == {"items": [], "total": 0, "skip": 0, "limit": 10}


@pytest.mark.asyncio
async def test_only_the_shop_owner_replies_and_can_edit_the_reply(client):
    shop = await make_shop(client)
    other_shop = await make_shop(client, owner="owner-2")
    await review(client, shop, "cust-1", 2, "Waited long")
    await review(client, shop, "cust-2", 5, "Great")
    first, second = (await reviews(client, shop))["items"]
    url = f"/api/v1/shops/{shop}/reviews/{second['id']}/reply"

    assert (await client.put(url, json={"text": "Thanks"})).status_code == 401
    assert (await client.put(url, json={"text": "Thanks"}, headers=auth("owner-2"))).status_code == 403
    assert (await client.put(url, json={"text": "Thanks"}, headers=auth("cust-1"))).status_code == 403
    assert (await client.put(url, json={"text": "   "}, headers=OWNER)).status_code == 422
    assert (await client.put(url, json={"text": "x" * 1001}, headers=OWNER)).status_code == 422
    # A review is replied to through its own shop only.
    wrong_shop = f"/api/v1/shops/{other_shop}/reviews/{second['id']}/reply"
    assert (await client.put(wrong_shop, json={"text": "Hi"}, headers=auth("owner-2"))).status_code == 404

    replied = await client.put(url, json={"text": " Sorry for the wait, Priya. "}, headers=OWNER)
    assert replied.status_code == 200
    reply = replied.json()["reply"]
    assert reply["text"] == "Sorry for the wait, Priya."
    edited = (await client.put(url, json={"text": "Sorry for the wait!"}, headers=OWNER)).json()["reply"]
    assert edited["text"] == "Sorry for the wait!"
    assert edited["created_at"] == reply["created_at"] and edited["updated_at"] >= reply["updated_at"]

    # Still one reply, shown publicly, and the owner can find what is left to answer.
    page = await reviews(client, shop)
    assert page["items"][1]["reply"]["text"] == "Sorry for the wait!"
    assert [i["id"] for i in (await reviews(client, shop, needs_reply=True))["items"]] == [first["id"]]

    removed = await client.delete(url, headers=OWNER)
    assert removed.status_code == 200 and removed.json()["reply"] is None
    assert (await reviews(client, shop, needs_reply=True))["total"] == 2


@pytest.mark.asyncio
async def test_reported_reviews_stay_up_until_an_admin_hides_them(client):
    shop = await make_shop(client)
    await review(client, shop, "cust-1", 1, "Rude staff, call me on 98xxxxxx")
    await review(client, shop, "cust-2", 5)
    bad = (await reviews(client, shop, rating=1))["items"][0]
    report_url = f"/api/v1/shops/{shop}/reviews/{bad['id']}/report"

    assert (await client.post(report_url, json={"reason": "Contains a phone number"})).status_code == 401
    assert (await client.post(report_url, json={"reason": "x"}, headers=OWNER)).status_code == 422
    assert (await client.post(report_url, json={"reason": "Contains a phone number"}, headers=OWNER)).status_code == 202
    # Reporting again is accepted but counted once.
    assert (await client.post(report_url, json={"reason": "Again"}, headers=OWNER)).status_code == 200
    assert (await client.post(report_url, json={"reason": "Abusive"}, headers=auth("cust-3"))).status_code == 202
    assert (
        await client.post(f"/api/v1/shops/{shop}/reviews/nope/report", json={"reason": "spam"}, headers=OWNER)
    ).status_code == 404

    # Still visible and still counted.
    assert (await reviews(client, shop))["total"] == 2
    assert (await client.get(f"/api/v1/shops/{shop}")).json()["average_rating"] == 3.0

    # Moderation is for admins only.
    assert (await client.get("/api/v1/reviews/reported", headers=OWNER)).status_code == 403
    assert (await client.get("/api/v1/reviews/reported")).status_code == 401
    queue = (await client.get("/api/v1/reviews/reported", headers=ADMIN)).json()
    assert queue["total"] == 1
    [item] = queue["items"]
    assert (item["id"], item["report_count"], item["is_hidden"]) == (bad["id"], 2, False)
    assert item["report_reasons"] == ["Contains a phone number", "Abusive"]

    vis_url = f"/api/v1/reviews/{bad['id']}/visibility"
    assert (await client.put(vis_url, json={"hidden": True}, headers=OWNER)).status_code == 403
    hidden = await client.put(vis_url, json={"hidden": True}, headers=ADMIN)
    assert hidden.status_code == 200 and hidden.json()["is_hidden"] is True

    # Hidden: gone from the listing, the summary and the shop's average; can't be reported or found.
    assert [i["rating"] for i in (await reviews(client, shop))["items"]] == [5]
    summary = (await client.get(f"/api/v1/shops/{shop}/reviews/summary")).json()
    assert (summary["average_rating"], summary["review_count"]) == (5.0, 1)
    shop_now = (await client.get(f"/api/v1/shops/{shop}")).json()
    assert (shop_now["average_rating"], shop_now["review_count"]) == (5.0, 1)
    assert (await client.post(report_url, json={"reason": "spam!"}, headers=auth("cust-2"))).status_code == 404
    assert (await client.get("/api/v1/reviews/reported", params={"hidden": True}, headers=ADMIN)).json()["total"] == 1
    assert (await client.get("/api/v1/reviews/reported", params={"hidden": False}, headers=ADMIN)).json()["total"] == 0

    shown = await client.put(vis_url, json={"hidden": False}, headers=ADMIN)
    assert shown.json()["is_hidden"] is False
    assert (await client.get(f"/api/v1/shops/{shop}")).json()["review_count"] == 2
    assert (
        await client.put("/api/v1/reviews/nope/visibility", json={"hidden": True}, headers=ADMIN)
    ).status_code == 404


@pytest.mark.asyncio
async def test_a_review_without_an_account_name_reads_as_a_verified_customer(client):
    shop = await make_shop(client)
    await review(client, shop, "cust-without-name", 3)
    assert (await reviews(client, shop))["items"][0]["reviewer_name"] == "Verified customer"


@pytest.mark.asyncio
async def test_the_display_name_comes_from_the_callers_own_account(monkeypatch):
    import httpx

    from app import dependencies

    seen = []

    def auth_service(request):
        seen.append((request.url.path, request.headers["authorization"]))
        return httpx.Response(200, json={"full_name": "meera kapoor", "email": "m@example.com"})

    real = httpx.AsyncClient
    monkeypatch.setattr(
        dependencies.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(auth_service), **kw)
    )
    caller = dependencies.Caller("cust-1", "user", "tok")
    assert await dependencies.fetch_display_name(caller) == "Meera K."
    assert seen == [("/api/v1/auth/me", "Bearer tok")]

    def down(request):
        return httpx.Response(503)

    monkeypatch.setattr(dependencies.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(down), **kw))
    assert await dependencies.fetch_display_name(caller) is None


@pytest.mark.asyncio
async def test_contact_details_in_reviews_and_replies_are_hidden(client):
    shop = await make_shop(client)
    await review(client, shop, "cust-1", 4, "Good, but call me on 98765 43210 next time")
    [item] = (await reviews(client, shop))["items"]
    assert item["comment"] == "Good, but call me on [hidden for your safety] next time"
    url = f"/api/v1/shops/{shop}/reviews/{item['id']}/reply"
    replied = await client.put(url, json={"text": "Thanks! WhatsApp us at shop@gmail.com"}, headers=OWNER)
    assert replied.json()["reply"]["text"] == "Thanks! [hidden for your safety] us at [hidden for your safety]"
    page = await client.get(f"/api/v1/shops/{shop}/reviews")
    assert "98765" not in page.text and "gmail" not in page.text
    # Reviewers are shown by display name only, with nothing that identifies or contacts them.
    assert page.json()["items"][0]["reviewer_name"] == "Priya S."
    assert not {"customer_id", "booking_id", "email", "phone", "full_name"} & set(page.json()["items"][0])
