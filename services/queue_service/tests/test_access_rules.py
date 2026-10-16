"""Queues are opened by the service's shop owner; customers join and leave as themselves."""

import pytest

from tests.helpers import ALICE, BOB, CALLED, auth, join


@pytest.mark.asyncio
async def test_queue_rules(client):
    assert (await client.post("/api/v1/queues", json={"service_id": "svc-1"})).status_code == 401
    assert (await client.post("/api/v1/queues", json={"service_id": "svc-1"}, headers=BOB)).status_code == 403
    assert (await client.post("/api/v1/queues", json={"service_id": "missing"}, headers=BOB)).status_code == 404
    queue = await client.post("/api/v1/queues", json={"service_id": "svc-1"}, headers=ALICE)
    assert queue.status_code == 201
    qid = queue.json()["id"]

    join = {"customer_id": "alice", "service_id": "svc-1"}
    assert (await client.post(f"/api/v1/queues/{qid}/join", json=join, headers=BOB)).status_code == 403
    assert (await client.get(f"/api/v1/queues/{qid}/position/alice", headers=BOB)).status_code == 403
    assert (await client.delete(f"/api/v1/queues/{qid}/entries/someone-elses", headers=BOB)).status_code == 404


@pytest.mark.asyncio
async def test_customers_can_find_a_services_open_queues(client):
    created = await client.post("/api/v1/queues", json={"service_id": "svc-1"}, headers=ALICE)
    assert (await client.get("/api/v1/queues", params={"service_id": "svc-1"})).status_code == 401
    found = await client.get("/api/v1/queues", params={"service_id": "svc-1"}, headers=BOB)
    assert [q["id"] for q in found.json()] == [created.json()["id"]]
    assert (await client.get("/api/v1/queues", params={"service_id": "other"}, headers=BOB)).json() == []


@pytest.mark.asyncio
async def test_positions_move_up_as_people_ahead_are_served_or_leave(client):
    qid = (await client.post("/api/v1/queues", json={"service_id": "svc-1"}, headers=ALICE)).json()["id"]
    first, second, third = [await join(client, qid, who) for who in ("c1", "c2", "c3")]
    assert [first["position"], second["position"], third["position"]] == [1, 2, 3]
    assert third["estimated_wait_minutes"] == 10
    # Joining again keeps your place instead of queueing twice.
    assert (await join(client, qid, "c2"))["id"] == second["id"]

    pos = lambda who: client.get(f"/api/v1/queues/{qid}/position/{who}", headers=auth(who))  # noqa: E731
    called = await client.post(f"/api/v1/queues/{qid}/next", headers=ALICE)
    assert called.json()["customer_id"] == "c1"
    # c1 is told it is their turn; c3 has moved near the front (c2 joined there, so was not told).
    assert CALLED == [("queue.called", ["c1"]), ("queue.almost_turn", ["c3"])]
    mine = (await pos("c1")).json()
    assert (mine["status"], mine["position"]) == ("CALLED", 0)  # their turn, not "not in queue"
    assert (await pos("c3")).json()["position"] == 2

    await client.delete(f"/api/v1/queues/{qid}/entries/{second['id']}", headers=auth("c2"))
    now = (await pos("c3")).json()
    assert {k: now[k] for k in ("status", "position", "people_ahead", "estimated_wait_minutes")} == {
        "status": "WAITING",
        "position": 1,
        "people_ahead": 0,
        "estimated_wait_minutes": 5,  # c1 is still being served
    }
    assert now["entry_id"] == third["id"] and now["estimated_call_at"]
    entries = (await client.get(f"/api/v1/queues/{qid}/entries", headers=ALICE)).json()
    assert [(e["customer_id"], e["status"], e["position"]) for e in entries] == [
        ("c1", "CALLED", 0),
        ("c3", "WAITING", 1),
    ]
    assert (await client.get(f"/api/v1/queues/{qid}", headers=BOB)).json()["current_size"] == 1

    await client.post(f"/api/v1/queues/{qid}/next", headers=ALICE)
    assert (await client.post(f"/api/v1/queues/{qid}/next", headers=ALICE)).json() is None


@pytest.mark.asyncio
async def test_only_the_shop_manages_its_queue(client):
    qid = (await client.post("/api/v1/queues", json={"service_id": "svc-1"}, headers=ALICE)).json()["id"]
    await join(client, qid, "c1")
    assert (await client.get(f"/api/v1/queues/{qid}/entries", headers=BOB)).status_code == 403
    assert (await client.post(f"/api/v1/queues/{qid}/next", headers=BOB)).status_code == 403
    assert (await client.patch(f"/api/v1/queues/{qid}", json={"is_accepting": False}, headers=BOB)).status_code == 403
    assert CALLED == []

    assert (await client.post("/api/v1/queues", json={"service_id": "svc-1"}, headers=ALICE)).status_code == 409
    closed = await client.patch(f"/api/v1/queues/{qid}", json={"is_accepting": False}, headers=ALICE)
    assert closed.json()["is_accepting"] is False
    late = await client.post(
        f"/api/v1/queues/{qid}/join", json={"customer_id": "c9", "service_id": "svc-1"}, headers=auth("c9")
    )
    assert late.status_code == 409
    # Customers no longer find it, but the shop still sees it to reopen.
    assert (await client.get("/api/v1/queues", params={"service_id": "svc-1"}, headers=BOB)).json() == []
    every = await client.get("/api/v1/queues", params={"service_id": "svc-1", "include_closed": True}, headers=ALICE)
    assert [q["id"] for q in every.json()] == [qid]
