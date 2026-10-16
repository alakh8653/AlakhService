"""Wait estimates follow staff and real service times; called customers are served or skipped."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import update

from app.database import get_db
from app.main import app
from app.models.queue import QueueEntry
from tests.helpers import ALICE, BOB, CALLED, auth, join


async def open_queue(client, **settings):
    resp = await client.post("/api/v1/queues", json={"service_id": "svc-1", **settings}, headers=ALICE)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def position(client, qid, who):
    return (await client.get(f"/api/v1/queues/{qid}/position/{who}", headers=auth(who))).json()


async def backdate_call(entry_id, minutes):
    """Pretends the customer was called `minutes` ago (writes through the test database)."""
    async for db in app.dependency_overrides[get_db]():
        await db.execute(
            update(QueueEntry)
            .where(QueueEntry.id == entry_id)
            .values(called_at=datetime.now(timezone.utc) - timedelta(minutes=minutes))
        )


async def entries(client, qid):
    return (await client.get(f"/api/v1/queues/{qid}/entries", headers=ALICE)).json()


@pytest.mark.asyncio
async def test_estimate_uses_staff_count_and_service_time(client):
    q = await open_queue(client, servers=2, avg_service_minutes=30)
    assert (q["servers"], q["avg_service_minutes"]) == (2, 30)
    for who in ("c1", "c2", "c3", "c4", "c5"):
        await join(client, q["id"], who)
    # Two chairs: c1 and c2 go straight in, c3 and c4 after one 30-minute round, c5 after two.
    waits = [(await position(client, q["id"], w))["estimated_wait_minutes"] for w in ("c1", "c2", "c3", "c4", "c5")]
    assert waits == [0, 0, 30, 30, 60]
    five = await position(client, q["id"], "c5")
    called_at = datetime.fromisoformat(five["estimated_call_at"])
    assert timedelta(minutes=59) < called_at - datetime.now(timezone.utc) <= timedelta(minutes=60)

    # A third stylist starts: the shop updates the queue and every estimate drops.
    patched = await client.patch(f"/api/v1/queues/{q['id']}", json={"servers": 3}, headers=ALICE)
    assert patched.json()["servers"] == 3
    assert (await position(client, q["id"], "c5"))["estimated_wait_minutes"] == 30
    assert (await client.patch(f"/api/v1/queues/{q['id']}", json={"servers": 0}, headers=ALICE)).status_code == 422
    assert (await client.patch(f"/api/v1/queues/{q['id']}", json={"servers": 4}, headers=BOB)).status_code == 403


@pytest.mark.asyncio
async def test_finished_services_teach_the_queue_its_real_service_time(client):
    q = await open_queue(client, avg_service_minutes=10)
    await join(client, q["id"], "c1")
    called = (await client.post(f"/api/v1/queues/{q['id']}/next", headers=ALICE)).json()
    assert called["called_at"]

    await backdate_call(called["id"], 20)  # the haircut took 20 minutes

    done = await client.post(f"/api/v1/queues/{q['id']}/entries/{called['id']}/complete", headers=ALICE)
    assert done.status_code == 200 and done.json()["status"] == "SERVED" and done.json()["finished_at"]
    # 0.7 x 10 + 0.3 x 20 = 13 minutes
    learned = (await client.get(f"/api/v1/queues/{q['id']}", headers=ALICE)).json()["avg_service_minutes"]
    assert learned == pytest.approx(13, abs=0.1)
    # Only a called customer can be completed, once, and only by the shop.
    again = await client.post(f"/api/v1/queues/{q['id']}/entries/{called['id']}/complete", headers=ALICE)
    assert again.status_code == 404
    assert (await client.post(f"/api/v1/queues/{q['id']}/entries/x/complete", headers=BOB)).status_code == 403


@pytest.mark.asyncio
async def test_a_mis_tapped_done_does_not_skew_the_average(client):
    q = await open_queue(client, avg_service_minutes=10)
    await join(client, q["id"], "c1")
    called = (await client.post(f"/api/v1/queues/{q['id']}/next", headers=ALICE)).json()
    # "Done" tapped seconds after calling: not a real service time, so nothing is learned.
    await client.post(f"/api/v1/queues/{q['id']}/entries/{called['id']}/complete", headers=ALICE)
    assert (await client.get(f"/api/v1/queues/{q['id']}", headers=ALICE)).json()["avg_service_minutes"] == 10


@pytest.mark.asyncio
async def test_no_shows_are_skipped_by_hand_or_after_the_grace_period(client):
    q = await open_queue(client, no_show_grace_minutes=10)
    for who in ("c1", "c2", "c3"):
        await join(client, q["id"], who)

    first = (await client.post(f"/api/v1/queues/{q['id']}/next", headers=ALICE)).json()
    skipped = await client.post(f"/api/v1/queues/{q['id']}/entries/{first['id']}/no-show", headers=ALICE)
    assert skipped.json()["status"] == "NO_SHOW"
    assert (await client.get(f"/api/v1/queues/{q['id']}/position/c1", headers=auth("c1"))).status_code == 404

    second = (await client.post(f"/api/v1/queues/{q['id']}/next", headers=ALICE)).json()
    assert second["customer_id"] == "c2"
    # c2 was called 11 minutes ago and never came: the next call skips them automatically.
    await backdate_call(second["id"], 11)
    third = (await client.post(f"/api/v1/queues/{q['id']}/next", headers=ALICE)).json()
    assert third["customer_id"] == "c3"
    statuses = {e["customer_id"]: e["status"] for e in await entries(client, q["id"])}
    assert statuses == {"c3": "CALLED"}  # c2 is no longer counted as being served


@pytest.mark.asyncio
async def test_almost_your_turn_is_sent_once_as_people_move_up(client):
    q = await open_queue(client, notify_ahead=1)
    for who in ("c1", "c2", "c3"):
        await join(client, q["id"], who)
    CALLED.clear()

    await client.post(f"/api/v1/queues/{q['id']}/next", headers=ALICE)  # c1 called; c2 is now first
    assert CALLED == [("queue.called", ["c1"]), ("queue.almost_turn", ["c2"])]
    CALLED.clear()

    # c2 leaves: c3 moves to the front and is told; nobody is told twice.
    c2 = await position(client, q["id"], "c2")
    await client.delete(f"/api/v1/queues/{q['id']}/entries/{c2['entry_id']}", headers=auth("c2"))
    assert CALLED == [("queue.almost_turn", ["c3"])]
    CALLED.clear()
    await client.post(f"/api/v1/queues/{q['id']}/next", headers=ALICE)
    assert CALLED == [("queue.called", ["c3"])]


@pytest.mark.asyncio
async def test_queue_settings_are_validated(client):
    for bad in ({"servers": 0}, {"avg_service_minutes": 0}, {"notify_ahead": -1}, {"max_capacity": 0}):
        resp = await client.post("/api/v1/queues", json={"service_id": "svc-1", **bad}, headers=ALICE)
        assert resp.status_code == 422, bad
