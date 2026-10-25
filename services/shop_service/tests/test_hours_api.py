"""Opening hours, holidays and capacity: public to read, the owner's to change."""

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.services import hours_service
from tests.test_staff_api import ADMIN, OTHER, OWNER

WEEK = {
    "weekly": [
        # A split shift on Monday, given out of order.
        {"day": 0, "intervals": [{"start": "16:00", "end": "20:00"}, {"start": "10:00", "end": "14:00"}]},
        {"day": 5, "intervals": [{"start": "09:00", "end": "24:00"}]},
    ]
}


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


@pytest_asyncio.fixture
async def shop(client):
    resp = await client.post(
        "/api/v1/shops", json={"owner_id": "owner-1", "name": "Glow Salon", "category": "salon"}, headers=OWNER
    )
    return resp.json()


def hours_url(shop):
    return f"/api/v1/shops/{shop['id']}/hours"


def today():
    return hours_service.today_in_shop_zone()


@pytest.mark.asyncio
async def test_a_new_shop_has_no_hours_yet_and_serves_one_customer_at_a_time(client, shop):
    resp = await client.get(hours_url(shop))
    assert resp.status_code == 200
    body = resp.json()
    assert body["configured"] is False
    assert body["timezone"] == "Asia/Kolkata"
    assert [d["day"] for d in body["weekly"]] == list(range(7))
    assert all(d["intervals"] == [] for d in body["weekly"])
    assert body["holidays"] == []
    assert (body["capacity"], body["capacity_override"], body["active_staff"]) == (1, None, 0)
    assert (await client.get("/api/v1/shops/nope/hours")).status_code == 404


@pytest.mark.asyncio
async def test_the_owner_publishes_a_week_with_a_split_shift_and_anyone_can_read_it(client, shop):
    assert (await client.put(hours_url(shop), json=WEEK)).status_code == 401
    assert (await client.put(hours_url(shop), json=WEEK, headers=OTHER)).status_code == 403

    saved = await client.put(hours_url(shop), json=WEEK, headers=OWNER)
    assert saved.status_code == 200
    public = (await client.get(hours_url(shop))).json()
    assert public == saved.json()
    assert public["configured"] is True
    assert public["weekly"][0]["intervals"] == [{"start": "10:00", "end": "14:00"}, {"start": "16:00", "end": "20:00"}]
    assert public["weekly"][5]["intervals"] == [{"start": "09:00", "end": "24:00"}]
    assert public["weekly"][1]["intervals"] == []  # left out: closed
    assert public["updated_at"] is not None


@pytest.mark.asyncio
async def test_saving_a_week_replaces_the_previous_one_and_an_all_closed_week_still_counts_as_set(client, shop):
    await client.put(hours_url(shop), json=WEEK, headers=OWNER)
    closed = await client.put(hours_url(shop), json={"weekly": []}, headers=ADMIN)
    assert closed.status_code == 200
    assert closed.json()["configured"] is True
    assert all(d["intervals"] == [] for d in closed.json()["weekly"])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "intervals, problem",
    [
        ([{"start": "14:00", "end": "10:00"}], "before the closing time"),
        ([{"start": "10:00", "end": "10:00"}], "before the closing time"),
        ([{"start": "10:10", "end": "14:00"}], "quarter hour"),
        ([{"start": "9:00", "end": "14:00"}], "not a time"),
        ([{"start": "10:00", "end": "24:30"}], "not a time of day"),
        ([{"start": "24:00", "end": "24:00"}], "cannot start at 24:00"),
        ([{"start": "10:00", "end": "14:00"}, {"start": "13:00", "end": "18:00"}], "overlap"),
        ([{"start": "10:00", "end": "14:00"}, {"start": "14:00", "end": "18:00"}], "merge them"),
        ([{"start": f"{h:02}:00", "end": f"{h:02}:30"} for h in range(8, 13)], "at most 4"),
    ],
)
async def test_bad_intervals_are_refused_with_a_reason(client, shop, intervals, problem):
    resp = await client.put(hours_url(shop), json={"weekly": [{"day": 2, "intervals": intervals}]}, headers=OWNER)
    assert resp.status_code == 422
    assert problem in str(resp.json()["detail"])
    assert (await client.get(hours_url(shop))).json()["configured"] is False


@pytest.mark.asyncio
async def test_a_day_listed_twice_or_out_of_range_is_refused(client, shop):
    twice = {"weekly": [{"day": 1, "intervals": []}, {"day": 1, "intervals": []}]}
    assert (await client.put(hours_url(shop), json=twice, headers=OWNER)).status_code == 422
    eighth = {"weekly": [{"day": 7, "intervals": []}]}
    assert (await client.put(hours_url(shop), json=eighth, headers=OWNER)).status_code == 422


@pytest.mark.asyncio
async def test_capacity_defaults_to_active_staff_and_the_owner_can_override_it(client, shop):
    for name in ("Asha", "Ravi", "Meena"):
        await client.post("/api/v1/staff", json={"shop_id": shop["id"], "name": name}, headers=OWNER)
    staff = (await client.get("/api/v1/staff", params={"shop_id": shop["id"]}, headers=OWNER)).json()
    await client.put(f"/api/v1/staff/{staff[0]['id']}", json={"is_active": False}, headers=OWNER)
    assert (await client.get(hours_url(shop))).json()["capacity"] == 2

    url = f"/api/v1/shops/{shop['id']}/capacity"
    assert (await client.put(url, json={"capacity": 5}, headers=OTHER)).status_code == 403
    assert (await client.put(url, json={"capacity": 0}, headers=OWNER)).status_code == 422
    set_ = (await client.put(url, json={"capacity": 5}, headers=OWNER)).json()
    assert (set_["capacity"], set_["capacity_override"], set_["active_staff"]) == (5, 5, 2)
    assert set_["configured"] is False  # capacity alone does not publish hours
    back = (await client.put(url, json={"capacity": None}, headers=OWNER)).json()
    assert (back["capacity"], back["capacity_override"]) == (2, None)


@pytest.mark.asyncio
async def test_holidays_are_added_listed_soonest_first_and_removed(client, shop):
    url = f"/api/v1/shops/{shop['id']}/holidays"
    later, sooner = today() + timedelta(days=20), today() + timedelta(days=3)
    assert (await client.post(url, json={"date": later.isoformat()}, headers=OTHER)).status_code == 403
    first = await client.post(url, json={"date": later.isoformat(), "note": "  "}, headers=OWNER)
    assert first.status_code == 201
    second = await client.post(url, json={"date": sooner.isoformat(), "note": "Diwali"}, headers=OWNER)
    assert second.json()["holidays"] == [
        {"date": sooner.isoformat(), "note": "Diwali"},
        {"date": later.isoformat(), "note": None},
    ]
    again = await client.post(url, json={"date": sooner.isoformat()}, headers=OWNER)
    assert again.status_code == 409
    assert "already a holiday" in again.json()["detail"]

    assert (await client.delete(f"{url}/{sooner.isoformat()}", headers=OTHER)).status_code == 403
    assert (await client.delete(f"{url}/{sooner.isoformat()}", headers=OWNER)).status_code == 204
    assert (await client.delete(f"{url}/{sooner.isoformat()}", headers=OWNER)).status_code == 404
    assert [h["date"] for h in (await client.get(hours_url(shop))).json()["holidays"]] == [later.isoformat()]


@pytest.mark.asyncio
async def test_holidays_in_the_past_or_more_than_a_year_ahead_are_refused(client, shop):
    url = f"/api/v1/shops/{shop['id']}/holidays"
    past = await client.post(url, json={"date": (today() - timedelta(days=1)).isoformat()}, headers=OWNER)
    assert past.status_code == 422
    assert "already passed" in past.json()["detail"]
    far = await client.post(url, json={"date": (today() + timedelta(days=400)).isoformat()}, headers=OWNER)
    assert far.status_code == 422
    assert (await client.post(url, json={"date": today().isoformat()}, headers=OWNER)).status_code == 201
    long_note = {"date": (today() + timedelta(days=1)).isoformat(), "note": "x" * 121}
    assert (await client.post(url, json=long_note, headers=OWNER)).status_code == 422


def test_today_is_the_date_in_india_not_in_utc(monkeypatch):
    class LateEvening(datetime):
        @classmethod
        def now(cls, tz=None):
            # 20:00 UTC on the 18th is 01:30 on the 19th in India.
            return datetime(2026, 10, 18, 20, 0, tzinfo=timezone.utc).astimezone(tz)

    monkeypatch.setattr(hours_service, "datetime", LateEvening)
    assert hours_service.today_in_shop_zone().isoformat() == "2026-10-19"
