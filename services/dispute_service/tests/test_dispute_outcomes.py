"""Resolving a dispute refunds or releases the money (payment_service) and settles the booking."""

import json

import httpx
import pytest
import pytest_asyncio

from app.core.settlement import SettlementClient, get_settlement_client
from app.main import app
from tests.test_dispute_api import B1, client, create  # noqa: F401  (client is a fixture)

CALLS: list = []
RESPONSES: dict = {}


def peers(request: httpx.Request) -> httpx.Response:
    """payment_service and booking_service's internal routes."""
    assert request.headers["x-internal-key"] == "k" * 40
    body = json.loads(request.content)
    CALLS.append((request.url.host, request.url.path, body))
    for suffix, response in RESPONSES.items():
        if request.url.path.endswith(suffix):
            if isinstance(response, Exception):
                raise response
            return response
    return httpx.Response(200, json={"ok": True})


@pytest_asyncio.fixture
async def http(client):  # noqa: F811
    CALLS.clear()
    RESPONSES.clear()
    app.dependency_overrides[get_settlement_client] = lambda: SettlementClient(
        "http://payment", "http://booking", "k" * 40, transport=httpx.MockTransport(peers)
    )
    yield client


async def resolve(http, dispute_id, **body):
    return await http.post(f"/api/v1/disputes/{dispute_id}/resolve", json={"resolution": "Decided", **body})


@pytest.mark.asyncio
async def test_full_refund(http):
    d = await create(http)
    resp = await resolve(http, d["id"], outcome="REFUND_FULL")
    assert resp.status_code == 200
    assert (resp.json()["status"], resp.json()["outcome"]) == ("RESOLVED", "REFUND_FULL")
    assert CALLS == [
        (
            "payment",
            f"/internal/payments/booking/{B1}/refund",
            {"amount_cents": None, "reason": f"Dispute {d['id']} resolved", "idempotency_key": f"dispute:{d['id']}"},
        ),
        ("booking", f"/internal/bookings/{B1}/resolve-dispute", {"outcome": "REFUNDED"}),
    ]


@pytest.mark.asyncio
async def test_partial_refund_needs_an_amount_and_completes_the_booking(http):
    d = await create(http)
    assert (await resolve(http, d["id"], outcome="REFUND_PARTIAL")).status_code == 422
    assert (await resolve(http, d["id"], outcome="REFUND_FULL", amount_cents=100)).status_code == 422
    assert CALLS == []
    resp = await resolve(http, d["id"], outcome="REFUND_PARTIAL", amount_cents=15000)
    assert resp.json()["refund_amount_cents"] == 15000
    assert CALLS[0][2]["amount_cents"] == 15000
    assert CALLS[1][2] == {"outcome": "COMPLETED"}


@pytest.mark.asyncio
async def test_release_to_shop(http):
    d = await create(http)
    assert (await resolve(http, d["id"], outcome="RELEASE_TO_SHOP")).status_code == 200
    assert [(h, p.rsplit("/", 1)[1], b) for h, p, b in CALLS] == [
        ("payment", "release", {}),
        ("booking", "resolve-dispute", {"outcome": "COMPLETED"}),
    ]


@pytest.mark.asyncio
async def test_no_action_touches_no_money(http):
    d = await create(http)
    assert (await resolve(http, d["id"])).json()["outcome"] == "NO_ACTION"
    assert CALLS == []


@pytest.mark.asyncio
async def test_a_payment_failure_resolves_nothing_and_can_be_retried(http):
    d = await create(http)
    RESPONSES["/refund"] = httpx.Response(502, json={"detail": "Razorpay could not process the refund"})
    failed = await resolve(http, d["id"], outcome="REFUND_FULL")
    assert failed.status_code == 502
    assert "Razorpay" in failed.json()["detail"]
    assert (await http.get(f"/api/v1/disputes/{d['id']}")).json()["status"] == "OPEN"
    assert [p.rsplit("/", 1)[1] for _, p, _ in CALLS] == ["refund"]  # the booking was left alone

    RESPONSES["/refund"] = httpx.Response(409, json={"detail": "This booking has no payment left to refund"})
    assert (await resolve(http, d["id"], outcome="REFUND_FULL")).status_code == 409

    RESPONSES["/refund"] = httpx.ConnectError("down")
    assert (await resolve(http, d["id"], outcome="REFUND_FULL")).status_code == 502

    RESPONSES.clear()
    assert (await resolve(http, d["id"], outcome="REFUND_FULL")).status_code == 200
    # Every try carried the same key, so payment_service refunds once.
    keys = {b["idempotency_key"] for _, p, b in CALLS if p.endswith("/refund")}
    assert keys == {f"dispute:{d['id']}"}


@pytest.mark.asyncio
async def test_a_booking_never_marked_disputed_is_left_as_it_is(http):
    d = await create(http)
    RESPONSES["/resolve-dispute"] = httpx.Response(409, json={"detail": "The booking is COMPLETED, not DISPUTED"})
    assert (await resolve(http, d["id"], outcome="RELEASE_TO_SHOP")).status_code == 200


@pytest.mark.asyncio
async def test_a_resolved_dispute_is_not_settled_again(http):
    d = await create(http)
    await resolve(http, d["id"], outcome="RELEASE_TO_SHOP")
    CALLS.clear()
    assert (await resolve(http, d["id"], outcome="REFUND_FULL")).status_code == 400
    assert CALLS == []


@pytest.mark.asyncio
async def test_only_admins_resolve(http):
    from tests.test_dispute_api import auth

    d = await create(http)
    resp = await http.post(
        f"/api/v1/disputes/{d['id']}/resolve",
        json={"resolution": "x", "outcome": "REFUND_FULL"},
        headers=auth("cust-1", "user"),
    )
    assert resp.status_code == 403
    assert CALLS == []
