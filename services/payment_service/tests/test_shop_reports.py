"""A shop's profit and loss, in India time, and reports reaching its owner once."""

import itertools
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.config import settings as reports_settings
from app.core import reports
from app.core.peers import get_shop_directory
from app.core.reports import due_reports, get_report_sender
from app.database import get_db
from app.main import app
from app.models.payment import ShopEarning, ShopReportDelivery
from app.services.report_service import period_range
from tests.test_earnings_api import KEY, OWNER, auth, http  # noqa: F401  (http is a fixture)
from tests.test_payment_access_api import client  # noqa: F401

SHOP = "shop-1"
BASE = f"/api/v1/payments/shops/{SHOP}"
INTERNAL = {"X-Internal-Key": KEY}


class FakeOwners:
    def __call__(self):
        async def lookup(shop_id):
            return "owner"

        return lookup


class FakeSender:
    def __init__(self, result=("app", "email")):
        self.sent = []
        self.result = result

    async def send(self, payload):
        self.sent.append(payload)
        return None if self.result is None else list(self.result)


class Directory:
    async def shop(self, shop_id):
        return {"id": shop_id, "owner_id": "owner", "name": "Ravi Salon"}


NUMBERS = itertools.count(1)


async def earning(moment, net=8000, gross=10000, collection="ONLINE", kind="SALE"):
    gen = app.dependency_overrides[get_db]()
    db = await gen.__anext__()
    db.add(
        ShopEarning(
            booking_id=f"b{next(NUMBERS)}",
            kind=kind,
            shop_id=SHOP,
            collection=collection,
            gross_cents=gross,
            commission_percent=Decimal("15"),
            gst_percent=Decimal("18"),
            commission_cents=gross - net,
            gst_cents=0,
            net_cents=net,
            payout_cents=net,
            status="READY",
            completed_at=moment,
        )
    )
    await db.commit()
    await gen.aclose()


@pytest.fixture
def owners():
    from app.dependencies import get_shop_owner_lookup

    app.dependency_overrides[get_shop_owner_lookup] = FakeOwners()
    yield


@pytest.fixture
def factory():
    class Factory:
        def __call__(self):
            return self

        async def __aenter__(self):
            self.gen = app.dependency_overrides[get_db]()
            return await self.gen.__anext__()

        async def __aexit__(self, *exc):
            await self.gen.aclose()

    return Factory()


def test_periods_including_indias_financial_year():
    day = date(2026, 11, 3)  # a Tuesday
    assert period_range("daily", day) == (day, day)
    assert period_range("weekly", day) == (date(2026, 11, 2), date(2026, 11, 8))
    assert period_range("monthly", day) == (date(2026, 11, 1), date(2026, 11, 30))
    assert period_range("monthly", date(2028, 2, 10)) == (date(2028, 2, 1), date(2028, 2, 29))
    assert period_range("yearly", day) == (date(2026, 4, 1), date(2027, 3, 31))
    assert period_range("yearly", date(2027, 3, 31)) == (date(2026, 4, 1), date(2027, 3, 31))
    assert period_range("yearly", date(2027, 4, 1)) == (date(2027, 4, 1), date(2028, 3, 31))


def test_which_reports_are_due_when():
    ist = timezone(timedelta(hours=5, minutes=30))
    assert due_reports(datetime(2026, 11, 3, 7, 59, tzinfo=ist)) == []
    assert due_reports(datetime(2026, 11, 3, 8, 0, tzinfo=ist)) == [("daily", date(2026, 11, 2))]
    assert [p for p, _ in due_reports(datetime(2026, 11, 2, 9, tzinfo=ist))] == ["daily", "weekly"]
    assert [p for p, _ in due_reports(datetime(2026, 12, 1, 9, tzinfo=ist))] == ["daily", "monthly"]
    assert [p for p, _ in due_reports(datetime(2027, 4, 1, 9, tzinfo=ist))] == ["daily", "monthly", "yearly"]


@pytest.mark.asyncio
async def test_profit_is_earnings_plus_income_less_expenses_and_tips_stay_out(http, owners):  # noqa: F811
    # 00:30 India time on the 10th is still the 9th in UTC: it belongs to the 10th.
    await earning(datetime(2026, 10, 9, 19, 0, tzinfo=timezone.utc), net=8000, gross=10000, collection="CASH")
    await earning(datetime(2026, 10, 10, 6, 0, tzinfo=timezone.utc), net=4000, gross=5000)
    await earning(datetime(2026, 10, 10, 7, 0, tzinfo=timezone.utc), net=500, gross=500, kind="TIP")
    for body in (
        {"kind": "EXPENSE", "category": "SPARE_PARTS", "amount": 30, "on_date": "2026-10-10"},
        {"kind": "EXPENSE", "category": "TRAVEL", "amount": 5, "on_date": "2026-10-10", "note": "Petrol"},
        {"kind": "INCOME", "category": "OUTSIDE_WORK", "amount": 25, "on_date": "2026-10-10"},
    ):
        assert (await http.post(f"{BASE}/cash-entries", json=body, headers=OWNER)).status_code == 201

    r = (await http.get(f"{BASE}/report", params={"period": "daily", "on": "2026-10-10"}, headers=OWNER)).json()
    assert (r["bookings"], r["gross"], r["cash"], r["online"]) == (2, 150.0, 100.0, 50.0)
    assert (r["earned"], r["other_income"], r["expenses"], r["tips"]) == (120.0, 25.0, 35.0, 5.0)
    assert r["profit"] == 110.0
    assert r["expenses_by_category"] == [
        {"category": "SPARE_PARTS", "amount": 30.0},
        {"category": "TRAVEL", "amount": 5.0},
    ]
    # The day before saw nothing in India time.
    before = (await http.get(f"{BASE}/report", params={"period": "daily", "on": "2026-10-09"}, headers=OWNER)).json()
    assert before["earned"] == 0
    assert r["profit_change_percent"] is None


@pytest.mark.asyncio
async def test_a_loss_and_the_comparison_with_the_period_before(http, owners):  # noqa: F811
    await earning(datetime(2026, 9, 15, 6, 0, tzinfo=timezone.utc), net=10000)
    await http.post(
        f"{BASE}/cash-entries",
        json={"kind": "EXPENSE", "category": "RENT", "amount": 300, "on_date": "2026-10-05"},
        headers=OWNER,
    )
    r = (await http.get(f"{BASE}/report", params={"period": "monthly", "on": "2026-10-20"}, headers=OWNER)).json()
    assert (r["label"], r["profit"], r["previous_profit"], r["profit_change_percent"]) == (
        "October 2026",
        -300.0,
        100.0,
        -400.0,
    )


@pytest.mark.asyncio
async def test_a_year_is_broken_down_by_month_and_can_be_downloaded(http, owners):  # noqa: F811
    await earning(datetime(2026, 5, 15, 6, 0, tzinfo=timezone.utc), net=10000)
    await earning(datetime(2026, 8, 15, 6, 0, tzinfo=timezone.utc), net=30000)
    params = {"period": "yearly", "on": "2026-11-03"}
    r = (await http.get(f"{BASE}/report", params=params, headers=OWNER)).json()
    assert r["label"] == "FY 2026-27"
    assert [b["label"] for b in r["breakdown"]] == ["May 2026", "Aug 2026"]
    assert r["best"] == "Aug 2026"
    resp = await http.get(f"{BASE}/report.csv", params=params, headers=OWNER)
    assert resp.headers["content-type"].startswith("text/csv")
    assert "Aug 2026,300.0,0.0,300.0" in resp.text


@pytest.mark.asyncio
async def test_entries_are_checked_and_can_be_removed(http, owners):  # noqa: F811
    url = f"{BASE}/cash-entries"
    bad = {"kind": "EXPENSE", "category": "TRAVEL", "amount": 5}
    assert (await http.post(url, json={**bad, "amount": 0}, headers=OWNER)).status_code == 422
    assert (await http.post(url, json={**bad, "category": "BRIBES"}, headers=OWNER)).status_code == 422
    future = (datetime.now(timezone.utc) + timedelta(days=3)).date().isoformat()
    assert (await http.post(url, json={**bad, "on_date": future}, headers=OWNER)).status_code == 422
    entry = (await http.post(url, json=bad, headers=OWNER)).json()
    assert [e["id"] for e in (await http.get(url, headers=OWNER)).json()] == [entry["id"]]
    assert (await http.delete(f"{url}/{entry['id']}", headers=OWNER)).status_code == 204
    assert (await http.get(url, headers=OWNER)).json() == []


@pytest.mark.asyncio
async def test_only_the_owner_sees_or_changes_any_of_it(http):  # noqa: F811
    from app.dependencies import get_shop_owner_lookup

    app.dependency_overrides[get_shop_owner_lookup] = FakeOwners()
    stranger = auth("someone-else")
    assert (await http.get(f"{BASE}/report", headers=stranger)).status_code == 404
    assert (await http.get(f"{BASE}/report-settings", headers=stranger)).status_code == 404
    entry = {"kind": "EXPENSE", "category": "TRAVEL", "amount": 5}
    assert (await http.post(f"{BASE}/cash-entries", json=entry, headers=stranger)).status_code == 404
    assert (await http.post(f"{BASE}/report/send", headers=stranger)).status_code == 404


@pytest.mark.asyncio
async def test_whatsapp_is_off_until_the_owner_says_yes_and_the_moment_is_kept(http, owners, factory):  # noqa: F811
    from app.models.payment import ShopReportPreference

    url = f"{BASE}/report-settings"
    settings = (await http.get(url, headers=OWNER)).json()
    assert (settings["email"], settings["whatsapp"], settings["daily"]) == (True, False, True)
    assert (await http.put(url, json={**settings, "whatsapp": True, "daily": False}, headers=OWNER)).status_code == 200
    saved = (await http.get(url, headers=OWNER)).json()
    assert (saved["whatsapp"], saved["daily"]) == (True, False)
    async with factory() as db:
        assert (await db.get(ShopReportPreference, SHOP)).whatsapp_consent_at is not None


@pytest.mark.asyncio
async def test_a_scheduled_report_goes_once_and_only_to_shops_with_something_to_report(http, factory):  # noqa: F811
    now = datetime(2026, 11, 3, 9, 0, tzinfo=timezone.utc)  # 2:30 PM India time, a Tuesday
    await earning(datetime(2026, 11, 2, 6, 0, tzinfo=timezone.utc))
    sender = FakeSender()
    assert await reports.run_once(factory, Directory(), sender, now) == 1
    payload = sender.sent[0]
    assert (payload["user_id"], payload["shop_name"], payload["email"], payload["whatsapp"]) == (
        "owner",
        "Ravi Salon",
        True,
        False,
    )
    assert payload["report"]["label"] == "02 Nov 2026"
    assert "You earned from bookings,80.0" in payload["csv"]
    # The next pass, or a second copy of the service, sends nothing more.
    assert await reports.run_once(factory, Directory(), sender, now) == 0
    assert len(sender.sent) == 1


@pytest.mark.asyncio
async def test_a_report_that_could_not_go_out_is_tried_again(http, factory):  # noqa: F811
    now = datetime(2026, 11, 3, 9, 0, tzinfo=timezone.utc)
    await earning(datetime(2026, 11, 2, 6, 0, tzinfo=timezone.utc))
    assert await reports.run_once(factory, Directory(), FakeSender(result=None), now) == 0
    async with factory() as db:
        assert (await db.execute(select(ShopReportDelivery))).scalars().all() == []
    assert await reports.run_once(factory, Directory(), FakeSender(), now) == 1


@pytest.mark.asyncio
async def test_an_owner_who_turned_a_period_off_does_not_get_it(http, owners, factory):  # noqa: F811
    now = datetime(2026, 11, 3, 9, 0, tzinfo=timezone.utc)
    await earning(datetime(2026, 11, 2, 6, 0, tzinfo=timezone.utc))
    settings = (await http.get(f"{BASE}/report-settings", headers=OWNER)).json()
    await http.put(f"{BASE}/report-settings", json={**settings, "daily": False}, headers=OWNER)
    sender = FakeSender()
    assert await reports.run_once(factory, Directory(), sender, now) == 0
    assert sender.sent == []


@pytest.mark.asyncio
async def test_send_now_says_where_it_went(http, owners):  # noqa: F811
    sender = FakeSender(result=("app", "email"))
    app.dependency_overrides[get_report_sender] = lambda: sender
    app.dependency_overrides[get_shop_directory] = Directory
    resp = await http.post(f"{BASE}/report/send", params={"period": "weekly"}, headers=OWNER)
    assert (resp.status_code, resp.json()) == (200, {"sent_to": ["app", "email"]})
    assert sender.sent[0]["report"]["period"] == "weekly"
    app.dependency_overrides[get_report_sender] = lambda: FakeSender(result=None)
    assert (await http.post(f"{BASE}/report/send", headers=OWNER)).status_code == 503


@pytest.mark.asyncio
async def test_send_now_is_limited_each_day_because_whatsapp_costs_money(http, owners, monkeypatch):  # noqa: F811
    monkeypatch.setattr(reports_settings, "REPORT_SENDS_PER_DAY", 2)
    sender = FakeSender()
    app.dependency_overrides[get_report_sender] = lambda: sender
    app.dependency_overrides[get_shop_directory] = Directory
    url = f"{BASE}/report/send"
    assert (await http.post(url, headers=OWNER)).status_code == 200
    assert (await http.post(url, headers=OWNER)).status_code == 200
    third = await http.post(url, headers=OWNER)
    assert third.status_code == 429 and "tomorrow" in third.json()["detail"]
    assert len(sender.sent) == 2


@pytest.mark.asyncio
async def test_a_failed_send_does_not_use_up_the_limit(http, owners, monkeypatch):  # noqa: F811
    monkeypatch.setattr(reports_settings, "REPORT_SENDS_PER_DAY", 1)
    app.dependency_overrides[get_shop_directory] = Directory
    app.dependency_overrides[get_report_sender] = lambda: FakeSender(result=None)
    url = f"{BASE}/report/send"
    assert (await http.post(url, headers=OWNER)).status_code == 503
    app.dependency_overrides[get_report_sender] = lambda: FakeSender()
    assert (await http.post(url, headers=OWNER)).status_code == 200


@pytest.mark.asyncio
async def test_what_a_shop_is_owed_and_forgetting_its_owners_notes(http, owners, factory):  # noqa: F811
    await earning(datetime(2026, 10, 10, 6, 0, tzinfo=timezone.utc), net=8000)
    resp = await http.get(f"/internal/payments/shops/{SHOP}/owed", headers=INTERNAL)
    assert (resp.status_code, resp.json()) == (200, {"owed_cents": 8000})
    assert (await http.get(f"/internal/payments/shops/{SHOP}/owed")).status_code in (401, 403)

    entry = {"kind": "EXPENSE", "category": "TRAVEL", "amount": 5}
    await http.post(f"{BASE}/cash-entries", json=entry, headers=OWNER)
    assert (await http.post(f"/internal/payments/shops/{SHOP}/forget", headers=INTERNAL)).status_code == 200
    assert (await http.get(f"{BASE}/cash-entries", headers=OWNER)).json() == []
    settings_now = (await http.get(f"{BASE}/report-settings", headers=OWNER)).json()
    assert not any(settings_now.values())
    # Its earnings stay, for the accounts the law says to keep.
    assert (await http.get(f"/internal/payments/shops/{SHOP}/owed", headers=INTERNAL)).json()["owed_cents"] == 8000
    # And nothing more goes out.
    sender = FakeSender()
    await earning(datetime(2026, 11, 2, 6, 0, tzinfo=timezone.utc))
    assert await reports.run_once(factory, Directory(), sender, datetime(2026, 11, 3, 9, 0, tzinfo=timezone.utc)) == 0
