"""Running the line on the day: walk-ins, the team's breaks, calling the next customer, learnt durations,
reordering, VIPs, no-shows, check-in and the public board."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.dependencies import get_team_lookup
from app.main import app
from app.models.booking import Booking
from app.models.queue import DurationStat, QueueAudit
from tests import test_availability
from tests.test_availability import CLOCK, MON, book, ist, utc_iso
from tests.test_shop_bookings_api import SENT, SESSIONS, auth, ws_client  # noqa: F401

TEAM = [
    {"id": "st-a", "name": "Asha", "service_ids": ["svc-a"]},
    {"id": "st-b", "name": "Bilal", "service_ids": ["svc-a", "svc-hour"]},
]
OWNER = auth("owner-1")
Q = "/api/v1/bookings/shop/shop-1/queue"


# The API client with test_availability's opening hours (capacity 2) and clock.
client = test_availability.client


@pytest.fixture(autouse=True)
def team(client):
    async def lookup(shop_id):
        return TEAM if shop_id == "shop-1" else []

    app.dependency_overrides[get_team_lookup] = lambda: lookup
    SENT.clear()
    yield
    app.dependency_overrides.pop(get_team_lookup, None)


async def walk_in(client, name, service="svc-a", **extra):
    resp = await client.post(
        "/api/v1/bookings/shop/shop-1/walk-ins", json={"service_id": service, "name": name, **extra}, headers=OWNER
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def line(client):
    resp = await client.get(Q, headers=OWNER)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def booked(client, customer, hhmm="10:00", confirm=True):
    resp = await book(client, MON, hhmm, customer=customer)
    assert resp.status_code == 201, resp.text
    if confirm:
        await client.put(f"/api/v1/bookings/{resp.json()['id']}/status", json={"status": "CONFIRMED"}, headers=OWNER)
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_a_walk_in_at_the_counter_gets_a_place_and_a_masked_name_on_the_board(client):
    CLOCK["now"] = ist(MON, "10:30")
    first = await walk_in(client, "Ravi Kumar")
    assert (first["source"], first["priority"], first["checked_in"], first["position"]) == (
        "WALK_IN",
        "WALK_IN",
        True,
        1,
    )
    assert first["customer_display_name"] == "Ravi Kumar" and first["staff_name"] in ("Asha", "Bilal")
    await walk_in(client, "Meena")
    third = await walk_in(client, "Kiran")
    assert third["position"] == 3 and third["eta_min"] <= third["estimated_start"] <= third["eta_max"]

    board = await client.get(f"{Q}/board")  # public
    assert board.status_code == 200
    body = board.json()
    assert [r["name"] for r in body["next"]] == ["R•••", "M••••", "K••••"] and body["waiting"] == 3
    assert "Ravi" not in board.text
    again = await client.get(f"{Q}/board", headers={"If-None-Match": board.headers["ETag"]})
    assert again.status_code == 304


@pytest.mark.asyncio
async def test_a_customer_joins_the_line_from_the_app_once_and_only_while_open(client):
    CLOCK["now"] = ist(MON, "10:30")
    joined = await client.post("/api/v1/bookings/walk-in", json={"service_id": "svc-a"}, headers=auth("j1"))
    assert joined.status_code == 201, joined.text
    assert joined.json()["state"] in ("WAITING", "YOUR_TURN") and joined.json()["staff_name"]
    twice = await client.post("/api/v1/bookings/walk-in", json={"service_id": "svc-a"}, headers=auth("j1"))
    assert twice.status_code == 409
    shop_told = [e for e, people, _ in SENT if e == "booking.created"]
    assert shop_told

    CLOCK["now"] = ist(MON, "15:00")  # between the two shifts
    closed = await client.post("/api/v1/bookings/walk-in", json={"service_id": "svc-a"}, headers=auth("j2"))
    assert closed.status_code == 409 and "closed" in closed.json()["detail"]


@pytest.mark.asyncio
async def test_a_break_moves_waiting_customers_to_whoever_else_can_serve_them(client):
    CLOCK["now"] = ist(MON, "10:30")
    a, b = await walk_in(client, "One"), await walk_in(client, "Two")
    assert {a["staff_name"], b["staff_name"]} == {"Asha", "Bilal"}  # one each, both now

    team = await client.put(f"{Q}/team/st-a", json={"status": "BREAK", "minutes": 30}, headers=OWNER)
    assert team.status_code == 200, team.text
    asha = next(m for m in team.json() if m["staff_id"] == "st-a")
    assert asha["status"] == "BREAK" and asha["until"]
    after = {e["booking_id"]: e for e in await line(client)}
    # Bilal takes the first now; the second waits for Asha back at 11:00 (sooner than Bilal at 11:15).
    plan = [(after[x["booking_id"]]["staff_name"], after[x["booking_id"]]["estimated_start"]) for x in (a, b)]
    assert plan == [("Bilal", utc_iso(MON, "10:30")), ("Asha", utc_iso(MON, "11:00"))]
    assert (await client.put(f"{Q}/team/st-a", json={"status": "BREAK"}, headers=OWNER)).status_code == 422
    assert (await client.put(f"{Q}/team/nobody", json={"status": "OFF"}, headers=OWNER)).status_code == 404

    async with SESSIONS["factory"]() as db:
        actions = (await db.execute(select(QueueAudit.action))).scalars().all()
    assert actions.count("walk_in") == 2 and "staff_status" in actions


@pytest.mark.asyncio
async def test_calling_the_next_customer_starts_them_and_a_finished_visit_teaches_its_length(client):
    CLOCK["now"] = ist(MON, "10:30")
    a, b = await walk_in(client, "One"), await walk_in(client, "Two")
    called = await client.post(f"{Q}/call-next", json={"staff_id": "st-a"}, headers=OWNER)
    assert called.status_code == 200, called.text
    assert (called.json()["state"], called.json()["staff_name"]) == ("IN_PROGRESS", "Asha")
    # Asha is busy: she cannot start a second customer at once.
    other = b if called.json()["booking_id"] == a["booking_id"] else a
    busy = await client.put(
        f"/api/v1/bookings/{other['booking_id']}/status",
        json={"status": "IN_PROGRESS", "staff_id": "st-a"},
        headers=OWNER,
    )
    assert busy.status_code == 409

    CLOCK["now"] = ist(MON, "11:00")  # 30 minutes for a 45-minute haircut
    done = await client.put(
        f"/api/v1/bookings/{called.json()['booking_id']}/status", json={"status": "COMPLETED"}, headers=OWNER
    )
    assert done.status_code == 200, done.text
    async with SESSIONS["factory"]() as db:
        stats = {(s.staff_id): (s.mean, s.n) for s in (await db.execute(select(DurationStat))).scalars()}
    assert stats == {"": (30.0, 1), "st-a": (30.0, 1)}

    # The shop's haircuts are now planned at 30 minutes, not the listed 45.
    third = await walk_in(client, "Three")
    planned = datetime.fromisoformat(third["estimated_end"]) - datetime.fromisoformat(third["estimated_start"])
    assert planned == timedelta(minutes=30)


@pytest.mark.asyncio
async def test_the_shop_reorders_the_line_and_makes_a_few_vips(client):
    CLOCK["now"] = ist(MON, "10:30")
    a, b, c = [await walk_in(client, name) for name in "ABC"]
    resp = await client.post(f"{Q}/reorder", json={"booking_ids": [c["booking_id"], b["booking_id"]]}, headers=OWNER)
    assert resp.status_code == 200, resp.text
    order = [e["booking_id"] for e in resp.json() if e["position"]]
    assert order == [c["booking_id"], b["booking_id"], a["booking_id"]]
    assert [e["moved"] for e in resp.json()] == [True, True, False]
    bad = await client.post(f"{Q}/reorder", json={"booking_ids": ["nope"]}, headers=OWNER)
    assert bad.status_code == 422
    assert (
        await client.post(f"{Q}/reorder", json={"booking_ids": [a["booking_id"]]}, headers=auth("c5"))
    ).status_code == 403

    await client.put(f"{Q}/settings", json={"vip_per_day": 1}, headers=OWNER)
    vip = await client.put(f"/api/v1/bookings/{a['booking_id']}/priority", json={"vip": True}, headers=OWNER)
    assert vip.status_code == 200, vip.text
    again = await client.put(f"/api/v1/bookings/{b['booking_id']}/priority", json={"vip": True}, headers=OWNER)
    assert again.status_code == 409
    vip_walk_in = await client.post(
        "/api/v1/bookings/shop/shop-1/walk-ins", json={"service_id": "svc-a", "name": "D", "vip": True}, headers=OWNER
    )
    assert vip_walk_in.status_code == 409


@pytest.mark.asyncio
async def test_a_no_show_after_the_grace_period_is_cancelled_and_the_customer_told(client):
    no_show = await booked(client, "ns1", "10:00")
    arrived = await booked(client, "ns2", "10:00")
    CLOCK["now"] = ist(MON, "10:05")
    early = await client.post(f"/api/v1/bookings/{no_show}/no-show", headers=OWNER)
    assert early.status_code == 409 and "10 minutes" in early.json()["detail"]
    assert (await client.post(f"/api/v1/bookings/{arrived}/check-in", headers=auth("ns2"))).status_code == 200

    CLOCK["now"] = ist(MON, "10:15")
    entries = {e["booking_id"]: e for e in await line(client)}
    assert entries[no_show]["can_mark_no_show"] and not entries[arrived]["can_mark_no_show"]
    assert (await client.post(f"/api/v1/bookings/{arrived}/no-show", headers=OWNER)).status_code == 409
    assert (await client.post(f"/api/v1/bookings/{no_show}/no-show", headers=auth("ns1"))).status_code == 403
    done = await client.post(f"/api/v1/bookings/{no_show}/no-show", headers=OWNER)
    assert done.status_code == 200, done.text
    async with SESSIONS["factory"]() as db:
        stored = await db.get(Booking, no_show)
    assert (stored.status, stored.cancellation_reason) == ("CANCELLED", "No-show")
    assert ("booking.no_show", [("ns1", "customer")]) in [(e, p) for e, p, _ in SENT]
    assert [e["booking_id"] for e in await line(client)] == [arrived]


@pytest.mark.asyncio
async def test_with_check_in_required_a_late_customer_is_out_of_line_until_they_arrive(client):
    put = await client.put(f"{Q}/settings", json={"check_in_required": True, "grace_minutes": 10}, headers=OWNER)
    assert put.status_code == 200 and put.json()["check_in_required"]
    late = await booked(client, "lc1", "10:00")
    CLOCK["now"] = ist(MON, "10:20")
    status = (await client.get(f"/api/v1/bookings/{late}/queue", headers=auth("lc1"))).json()
    assert (status["state"], status["can_check_in"]) == ("CHECK_IN_NEEDED", True)
    walked = await walk_in(client, "On time")  # arrived at 10:20 too, and ahead in the line
    assert walked["position"] == 1
    checked = await client.post(f"/api/v1/bookings/{late}/check-in", headers=auth("lc1"))
    assert checked.status_code == 200, checked.text
    body = checked.json()
    assert body["checked_in"] and not body["can_check_in"] and body["state"] in ("WAITING", "YOUR_TURN")
    assert (await client.post(f"/api/v1/bookings/{late}/check-in", headers=auth("stranger"))).status_code == 404


@pytest.mark.asyncio
async def test_settings_are_the_shops_and_checked(client):
    got = await client.get(f"{Q}/settings", headers=OWNER)
    assert got.json() == {
        "buffer_pct": 0.0, "alpha": 0.2, "grace_minutes": 10, "aging_minutes": 20, "check_in_required": False,
        "vip_per_day": 5,
    }  # fmt: skip
    assert (await client.put(f"{Q}/settings", json={"buffer_pct": 2}, headers=OWNER)).status_code == 422
    assert (await client.get(f"{Q}/settings", headers=auth("c5"))).status_code == 403


@pytest.mark.asyncio
async def test_a_service_nobody_on_the_team_does_is_flagged(client):
    CLOCK["now"] = ist(MON, "10:30")
    hour = await walk_in(client, "Long", service="svc-hour")
    assert hour["staff_name"] == "Bilal"
    team = TEAM[1]
    TEAM.remove(team)
    try:
        entry = next(e for e in await line(client) if e["booking_id"] == hour["booking_id"])
        assert (entry["state"], entry["reason"]) == ("UNSERVABLE", "NO_ELIGIBLE_WORKER")
    finally:
        TEAM.append(team)


@pytest.mark.asyncio
async def test_the_queue_still_works_when_the_team_cannot_be_fetched(client):
    async def down(shop_id):
        raise RuntimeError("shop_service down")

    app.dependency_overrides[get_team_lookup] = lambda: down
    CLOCK["now"] = ist(MON, "10:30")
    a = await walk_in(client, "A")
    assert a["position"] == 1 and a["staff_name"] is None  # the shop's two places instead
    assert (await client.get(f"{Q}/team", headers=OWNER)).json() == []


def test_the_shops_screen_gets_the_line_live_and_strangers_are_refused(ws_client):  # noqa: F811
    from fastapi.websockets import WebSocketDisconnect

    from app.core.payments import get_session_factory
    from app.dependencies import get_clock
    from tests.test_availability import HOURS
    from tests.test_shop_bookings_api import SCHEDULES

    async def lookup(shop_id):
        return TEAM

    SCHEDULES["shop-1"] = HOURS
    CLOCK["now"] = ist(MON, "10:30")
    app.dependency_overrides[get_clock] = lambda: lambda: CLOCK["now"]
    app.dependency_overrides[get_session_factory] = lambda: SESSIONS["factory"]
    app.dependency_overrides[get_team_lookup] = lambda: lookup
    token = OWNER["Authorization"].split()[1]
    with ws_client.websocket_connect(f"/api/v1/ws/shops/shop-1/queue?token={token}") as ws:
        first = ws.receive_json()
        assert (first["type"], first["entries"]) == ("queue", [])
        walked = ws_client.post(
            "/api/v1/bookings/shop/shop-1/walk-ins", json={"service_id": "svc-a", "name": "Live"}, headers=OWNER
        )
        assert walked.status_code == 201, walked.text
        update = ws.receive_json()  # straight away, not at the next refresh
        assert [e["customer_display_name"] for e in update["entries"]] == ["Live"]
        assert update["version"] != first["version"]
        ws.send_text("ping")
        assert ws.receive_json() == {"type": "pong"}
        with ws_client.websocket_connect("/api/v1/ws/shops/shop-1/board") as board:
            frame = board.receive_json()
            assert frame["type"] == "board" and [r["name"] for r in frame["next"]] == ["L•••"]

    for query, code in (
        ("", 4401),
        ("?token=bad", 4401),
        (f"?token={auth('owner-2')['Authorization'].split()[1]}", 4403),
    ):
        with pytest.raises(WebSocketDisconnect) as refused:
            with ws_client.websocket_connect(f"/api/v1/ws/shops/shop-1/queue{query}") as ws:
                ws.receive_json()
        assert refused.value.code == code


@pytest.mark.asyncio
async def test_the_team_view_says_when_someone_with_their_own_hours_works_today(client, monkeypatch):
    week = [{"day": 0, "intervals": [{"start": "12:00", "end": "14:00"}]}]
    monkeypatch.setitem(TEAM[1], "working_hours", week)
    CLOCK["now"] = ist(MON, "10:30")
    team = {m["staff_id"]: m for m in (await client.get(f"{Q}/team", headers=OWNER)).json()}
    assert team["st-a"]["works_today"] is None  # the shop's hours
    assert [
        (datetime.fromisoformat(s["start"]), datetime.fromisoformat(s["end"])) for s in team["st-b"]["works_today"]
    ] == [(ist(MON, "12:00"), ist(MON, "14:00"))]
