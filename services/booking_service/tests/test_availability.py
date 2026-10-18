"""Bookable times follow the shop's opening hours, holidays and capacity, and POST /bookings enforces them."""

import asyncio
import os
import uuid
from datetime import date, datetime, timedelta, timezone

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app import dependencies
from app.core.availability import max_concurrent, step_minutes
from app.dependencies import get_clock
from app.main import app
from app.models.booking import Booking
from tests.test_shop_bookings_api import LISTINGS, SCHEDULES, SESSIONS, auth, close_service, open_service

IST = timezone(timedelta(hours=5, minutes=30))
MON, TUE, WED, THU = date(2030, 11, 4), date(2030, 11, 5), date(2030, 11, 6), date(2030, 11, 7)
DIWALI = date(2030, 11, 8)

LISTINGS["svc-hour"] = {
    "id": "svc-hour",
    "shop_id": "shop-1",
    "price_cents": 1000,
    "duration_minutes": 60,
    "is_active": True,
}
LISTINGS["svc-other-shop"] = {
    "id": "svc-other-shop",
    "shop_id": "shop-2",
    "price_cents": 1000,
    "duration_minutes": 45,
    "is_active": True,
}


def interval(start, end):
    return {"start": start, "end": end}


HOURS = {
    "shop_id": "shop-1",
    "timezone": "Asia/Kolkata",
    "configured": True,
    "capacity": 2,
    "weekly": [
        {"day": 0, "intervals": [interval("10:00", "14:00"), interval("16:00", "20:00")]},  # split shift
        {"day": 1, "intervals": [interval("10:00", "22:00")]},
        {"day": 2, "intervals": [interval("09:00", "24:00")]},  # open till midnight
        {"day": 3, "intervals": []},  # closed on Thursdays
        {"day": 4, "intervals": [interval("10:00", "18:00")]},
        {"day": 5, "intervals": [interval("10:00", "18:00")]},
        {"day": 6, "intervals": [interval("10:00", "18:00")]},
    ],
    "holidays": [{"date": DIWALI.isoformat(), "note": "Diwali"}],
}


def ist(day: date, hhmm: str) -> datetime:
    hours, minutes = map(int, hhmm.split(":"))
    return datetime(day.year, day.month, day.day, hours, minutes, tzinfo=IST)


def utc_iso(day: date, hhmm: str) -> str:
    return ist(day, hhmm).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


CLOCK = {}


@pytest_asyncio.fixture
async def client():
    engine = await open_service()
    SCHEDULES["shop-1"] = HOURS
    # Sunday 3 Nov 2030, 8 AM in India, unless a test moves it.
    CLOCK["now"] = ist(date(2030, 11, 3), "08:00")
    app.dependency_overrides[get_clock] = lambda: lambda: CLOCK["now"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    await close_service(engine)


async def slots(client, day: date, service="svc-a"):
    resp = await client.get("/api/v1/availability", params={"service_id": service, "date": day.isoformat()})
    assert resp.status_code == 200, resp.text
    return resp.json()


def times(body):
    return [s["time"] for s in body["slots"]]


async def seed(*bookings):
    """Bookings of (shop, IST day, "HH:MM", minutes, status)."""
    async with SESSIONS["factory"]() as db:
        for shop, day, hhmm, minutes, status in bookings:
            at = ist(day, hhmm).astimezone(timezone.utc)
            db.add(
                Booking(
                    id=str(uuid.uuid4()),
                    booking_number=uuid.uuid4().hex[:10],
                    customer_id="someone",
                    service_id="svc-a",
                    shop_id=shop,
                    status=status,
                    scheduled_at=at,
                    duration_minutes=minutes,
                    total_amount=1000,
                    created_at=at,
                    updated_at=at,
                )
            )
        await db.commit()


def book(client, day: date, hhmm: str, service="svc-a", customer="c5", **extra):
    body = {"service_id": service, "scheduled_at": utc_iso(day, hhmm), **extra}
    return client.post("/api/v1/bookings", json=body, headers=auth(customer))


@pytest.mark.asyncio
async def test_a_shop_without_hours_says_so_and_still_takes_any_future_time(client):
    SCHEDULES.pop("shop-1")
    body = await slots(client, MON)
    assert (body["hours_configured"], body["status"], body["slots"]) == (False, "NOT_CONFIGURED", [])
    assert body["capacity"] is None
    assert (await book(client, MON, "03:10")).status_code == 201


@pytest.mark.asyncio
async def test_a_split_shift_offers_only_starts_whose_whole_booking_fits_an_interval(client):
    body = await slots(client, MON)  # a 45-minute haircut
    assert (body["hours_configured"], body["status"], body["message"]) == (True, "AVAILABLE", None)
    assert (body["duration_minutes"], body["step_minutes"], body["lead_time_minutes"]) == (45, 15, 30)
    assert body["open_intervals"] == [interval("10:00", "14:00"), interval("16:00", "20:00")]
    offered = times(body)
    assert offered[:3] == ["10:00", "10:15", "10:30"]
    assert "13:15" in offered and "13:30" not in offered  # would run past 14:00
    assert not [t for t in offered if "13:30" <= t < "16:00"]
    assert offered[-1] == "19:15"
    assert len(offered) == 2 * 14
    first = body["slots"][0]
    assert first == {"start": "2030-11-04T04:30:00Z", "time": "10:00", "remaining": 2}


@pytest.mark.asyncio
async def test_services_in_whole_half_hours_are_offered_half_hourly(client):
    assert step_minutes(60) == step_minutes(120) == 30 and step_minutes(45) == step_minutes(20) == 15
    offered = times(await slots(client, MON, "svc-hour"))
    assert offered == ["10:00", "10:30", "11:00", "11:30", "12:00", "12:30", "13:00"] + [
        "16:00",
        "16:30",
        "17:00",
        "17:30",
        "18:00",
        "18:30",
        "19:00",
    ]


@pytest.mark.asyncio
async def test_closed_weekdays_and_holidays_have_no_times_and_say_why(client):
    closed = await slots(client, THU)
    assert (closed["status"], closed["message"], closed["slots"]) == ("CLOSED", "Closed on this day", [])
    holiday = await slots(client, DIWALI)  # a Friday, normally open
    assert (holiday["status"], holiday["holiday_note"]) == ("HOLIDAY", "Diwali")
    assert holiday["message"] == "Closed on this day (Diwali)"

    refused = await book(client, DIWALI, "11:00")
    assert refused.status_code == 409
    assert refused.json()["detail"] == "The shop is closed on Fri 8 Nov (Diwali)"
    assert (await book(client, THU, "11:00")).status_code == 409


@pytest.mark.asyncio
async def test_a_service_longer_than_any_interval_that_day_is_closed_that_day(client):
    LISTINGS["svc-long"] = {**LISTINGS["svc-hour"], "id": "svc-long", "duration_minutes": 300}
    try:
        assert (await slots(client, MON, "svc-long"))["status"] == "CLOSED"  # 4-hour shifts
        assert (await slots(client, TUE, "svc-long"))["status"] == "AVAILABLE"
    finally:
        del LISTINGS["svc-long"]


@pytest.mark.asyncio
async def test_today_starts_half_an_hour_from_now_and_ends_with_no_more_today(client):
    CLOCK["now"] = ist(MON, "11:05")
    assert times(await slots(client, MON))[0] == "11:45"
    assert times(await slots(client, MON, "svc-hour"))[0] == "12:00"
    # Picked a moment ago and only just inside the half hour: still taken; clearly too soon: refused.
    assert (await book(client, MON, "11:30")).status_code == 201
    soon = await book(client, MON, "11:15", customer="c6")
    assert soon.status_code == 409
    assert "at least 30 minutes ahead" in soon.json()["detail"]

    CLOCK["now"] = ist(MON, "19:00")
    late = await slots(client, MON)
    assert (late["status"], late["message"]) == ("NO_MORE_TODAY", "No more times today — try another day")


@pytest.mark.asyncio
async def test_dates_are_from_today_up_to_fourteen_days_ahead(client):
    today = date(2030, 11, 3)
    params = {"service_id": "svc-a"}
    past = await client.get("/api/v1/availability", params={**params, "date": (today - timedelta(days=1)).isoformat()})
    assert past.status_code == 422
    far = await client.get("/api/v1/availability", params={**params, "date": (today + timedelta(days=15)).isoformat()})
    assert far.status_code == 422
    assert (await slots(client, today + timedelta(days=14)))["status"] == "AVAILABLE"
    assert (await client.get("/api/v1/availability", params={**params, "date": "3/11/2030"})).status_code == 422
    missing = await client.get("/api/v1/availability", params={"service_id": "nope", "date": MON.isoformat()})
    assert missing.status_code == 404
    off = await client.get("/api/v1/availability", params={"service_id": "svc-off", "date": MON.isoformat()})
    assert off.status_code == 409


@pytest.mark.asyncio
async def test_the_day_is_the_shops_day_in_india_not_the_utc_day(client):
    # 19:00 UTC on Tuesday is already 00:30 on Wednesday in India.
    CLOCK["now"] = datetime(2030, 11, 5, 19, 0, tzinfo=timezone.utc)
    assert (await slots(client, WED))["status"] == "AVAILABLE"  # today, though UTC still says the 5th
    yesterday = await client.get("/api/v1/availability", params={"service_id": "svc-a", "date": TUE.isoformat()})
    assert yesterday.status_code == 422
    late = (await slots(client, WED))["slots"][-1]
    assert late == {"start": "2030-11-06T17:45:00Z", "time": "23:15", "remaining": 2}  # ends at midnight

    # Tuesday 19:30 UTC is inside Tuesday's hours in UTC terms, but it is Wednesday 01:00 in the shop.
    at_one_am = await client.post(
        "/api/v1/bookings",
        json={"service_id": "svc-a", "scheduled_at": "2030-11-05T19:30:00Z"},
        headers=auth("c5"),
    )
    assert at_one_am.status_code == 409
    assert "Wed 6 Nov, 1:00 AM" in at_one_am.json()["detail"]
    assert (await book(client, WED, "23:00", "svc-hour")).status_code == 201  # ends exactly at 24:00
    assert (await book(client, WED, "23:15", "svc-hour")).status_code == 409  # would end after midnight


@pytest.mark.asyncio
async def test_a_time_held_by_as_many_bookings_as_the_capacity_is_not_offered_or_taken(client):
    await seed(("shop-1", MON, "10:00", 45, "PENDING"), ("shop-1", MON, "10:00", 45, "CONFIRMED"))
    body = await slots(client, MON)
    assert times(body)[0] == "10:45"  # 10:00-10:30 starts overlap both; a booking ending at 10:45 frees it
    assert body["slots"][0]["remaining"] == 2

    full = await book(client, MON, "10:30")
    assert full.status_code == 409
    assert full.json()["detail"] == "Mon 4 Nov, 10:30 AM is fully booked; pick another time"
    assert (await book(client, MON, "10:45")).status_code == 201
    one_left = next(s for s in (await slots(client, MON))["slots"] if s["time"] == "11:00")
    assert one_left["remaining"] == 1


@pytest.mark.asyncio
async def test_capacity_counts_bookings_at_the_same_moment_not_every_overlap(client):
    # Back to back: a 60-minute request at 12:30 overlaps both, but shares the shop with one at a time.
    await seed(("shop-1", MON, "12:00", 45, "ASSIGNED"), ("shop-1", MON, "12:45", 45, "IN_PROGRESS"))
    assert next(s for s in (await slots(client, MON, "svc-hour"))["slots"] if s["time"] == "12:30")["remaining"] == 1
    # Another 12:00-12:45 makes 12:30-12:45 full.
    await seed(("shop-1", MON, "12:00", 45, "PROVIDER_EN_ROUTE"))
    assert "12:30" not in times(await slots(client, MON, "svc-hour"))
    assert (await book(client, MON, "12:30", "svc-hour")).status_code == 409
    assert (await book(client, MON, "13:00", "svc-hour")).status_code == 201


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status", ["PENDING", "CONFIRMED", "ASSIGNED", "PROVIDER_EN_ROUTE", "PICKED_UP", "IN_PROGRESS"]
)
async def test_every_active_status_holds_a_place(client, status):
    SCHEDULES["shop-1"] = {**HOURS, "capacity": 1}
    await seed(("shop-1", MON, "16:00", 45, status))
    assert "16:00" not in times(await slots(client, MON))


@pytest.mark.asyncio
async def test_finished_cancelled_and_returning_bookings_and_other_shops_hold_no_place(client):
    SCHEDULES["shop-1"] = {**HOURS, "capacity": 1}
    await seed(
        ("shop-1", MON, "16:00", 45, "CANCELLED"),
        ("shop-1", MON, "16:00", 45, "COMPLETED"),
        ("shop-1", MON, "16:00", 45, "OUT_FOR_DELIVERY"),
        ("shop-2", MON, "16:00", 45, "CONFIRMED"),
    )
    assert next(s for s in (await slots(client, MON))["slots"] if s["time"] == "16:00")["remaining"] == 1
    assert (await book(client, MON, "16:00")).status_code == 201
    assert (await book(client, MON, "16:00", customer="c6")).status_code == 409  # now the one place is taken


@pytest.mark.asyncio
async def test_a_booking_starting_before_opening_still_holds_its_place_once_open(client):
    SCHEDULES["shop-1"] = {**HOURS, "capacity": 1}
    # Made before the shop published hours that open at 09:00; it runs until 10:00.
    await seed(("shop-1", WED, "08:00", 120, "CONFIRMED"))
    assert times(await slots(client, WED))[0] == "10:00"


@pytest.mark.asyncio
async def test_pickup_and_home_visits_use_the_pickup_or_visit_time_with_the_same_rules(client):
    repair = await slots(client, MON, "svc-repair")  # two hours
    assert times(repair) == ["10:00", "10:30", "11:00", "11:30", "12:00", "16:00", "16:30", "17:00", "17:30", "18:00"]
    pickup = {"service_mode": "PICKUP_DROP", "address_id": "addr-1", "item_description": "Laptop"}
    late = await book(client, MON, "13:00", "svc-repair", **pickup)
    assert late.status_code == 409
    assert "not open for the whole of a 120-minute booking" in late.json()["detail"]
    assert (await book(client, MON, "16:00", "svc-repair", **pickup)).status_code == 201
    home = {"service_mode": "AT_HOME", "address_id": "addr-1"}
    assert (await book(client, THU, "11:00", "svc-home", **home)).status_code == 409
    assert (await book(client, MON, "17:00", "svc-home", **home)).status_code == 201


@pytest.mark.asyncio
async def test_times_off_the_quarter_hour_are_refused(client):
    resp = await book(client, MON, "10:10")
    assert resp.status_code == 409
    assert "quarter hour" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_a_retry_of_a_booking_already_made_is_answered_even_once_the_time_is_full(client):
    SCHEDULES["shop-1"] = {**HOURS, "capacity": 1}
    body = {"service_id": "svc-a", "scheduled_at": utc_iso(MON, "10:00")}
    headers = {**auth("c5"), "Idempotency-Key": "k-1"}
    first = await client.post("/api/v1/bookings", json=body, headers=headers)
    again = await client.post("/api/v1/bookings", json=body, headers=headers)
    assert (first.status_code, again.status_code) == (201, 200)
    assert again.json()["id"] == first.json()["id"]


def test_max_concurrent_treats_touching_bookings_as_apart():
    t = datetime(2030, 1, 1, tzinfo=timezone.utc)
    h = timedelta(hours=1)
    assert max_concurrent([], t, t + h) == 0
    assert max_concurrent([(t, t + h), (t + h, t + 2 * h)], t, t + 2 * h) == 1
    assert max_concurrent([(t, t + 2 * h), (t + h, t + 3 * h)], t, t + 3 * h) == 2
    assert max_concurrent([(t, t + 2 * h), (t + h, t + 3 * h)], t + 2 * h, t + 3 * h) == 1  # clipped to the window
    assert max_concurrent([(t - h, t)], t, t + h) == 0


@pytest.mark.asyncio
async def test_shop_hours_are_fetched_with_the_id_escaped_cached_briefly_and_503_when_down(monkeypatch):
    paths, replies = [], {"status": 200}

    def shop_service(request):
        paths.append(request.url.raw_path)
        if replies["status"] == "down":
            raise httpx.ConnectError("refused")
        return httpx.Response(replies["status"], json={"configured": True})

    real = httpx.AsyncClient
    monkeypatch.setattr(
        dependencies.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(shop_service), **kw)
    )
    dependencies._schedule_cache.clear()
    assert await dependencies.fetch_shop_schedule("../admin") == {"configured": True}
    assert await dependencies.fetch_shop_schedule("../admin") == {"configured": True}
    assert paths == [b"/api/v1/shops/%2E%2E%2Fadmin/hours"]  # the second came from the cache

    replies["status"] = 404
    assert await dependencies.fetch_shop_schedule("gone") is None
    replies["status"] = "down"
    with pytest.raises(dependencies.HTTPException) as down:
        await dependencies.fetch_shop_schedule("shop-x")
    assert down.value.status_code == 503
    monkeypatch.setattr(dependencies.time, "monotonic", lambda: 10**12)  # the cache has expired
    with pytest.raises(dependencies.HTTPException):
        await dependencies.fetch_shop_schedule("../admin")
    dependencies._schedule_cache.clear()


needs_postgres = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL", "").startswith("postgresql"), reason="races need PostgreSQL"
)


@needs_postgres
@pytest.mark.asyncio
async def test_customers_racing_for_the_last_place_get_one_booking_between_them(client):
    SCHEDULES["shop-1"] = {**HOURS, "capacity": 1}
    replies = await asyncio.gather(*[book(client, MON, "10:00", customer=f"racer-{i}") for i in range(8)])
    assert sorted(r.status_code for r in replies) == [201] + [409] * 7


@pytest.mark.asyncio
async def test_a_day_with_every_place_taken_is_fully_booked(client):
    SCHEDULES["shop-1"] = {**HOURS, "capacity": 1}
    await seed(("shop-1", MON, "10:00", 240, "CONFIRMED"), ("shop-1", MON, "16:00", 240, "PENDING"))
    body = await slots(client, MON)
    assert (body["status"], body["message"], body["slots"]) == ("FULLY_BOOKED", "Fully booked — try another day", [])
