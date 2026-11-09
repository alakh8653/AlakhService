"""The live queue's Prometheus metrics (app/core/metrics.py)."""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

from app.core import metrics, queue_ops, worker
from app.core.notifier import Notifier
from app.main import app

NOW = datetime(2026, 10, 30, 10, 0, tzinfo=timezone.utc)


def value(name: str, **labels) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


def test_metrics_page_lists_the_queue_metrics():
    body = TestClient(app).get("/metrics").text
    for name in (
        "alakh_queue_request_seconds",
        "alakh_booking_worker_pass_seconds",
        "alakh_booking_worker_last_pass_timestamp_seconds",
        "alakh_booking_notifications_total",
        "alakh_queue_start_error_minutes_total",
    ):
        assert name in body


def test_only_the_queue_pages_are_timed():
    small = FastAPI()
    metrics.install_metrics(small)

    @small.get("/api/v1/bookings/shop/{shop_id}/queue/board")
    async def board(shop_id: str):
        return {}

    @small.get("/api/v1/bookings/{booking_id}")
    async def booking(booking_id: str):
        return {}

    client = TestClient(small)
    before = value("alakh_queue_request_seconds_count", endpoint="board")
    client.get("/api/v1/bookings/shop/s1/queue/board")
    client.get("/api/v1/bookings/shop/s2/queue/board")
    client.get("/api/v1/bookings/b1")
    assert value("alakh_queue_request_seconds_count", endpoint="board") == before + 2
    assert value("alakh_queue_request_seconds_count", endpoint="customer") == 0


def test_a_start_counts_its_distance_from_what_the_customer_was_told():
    booking = SimpleNamespace(
        id="b-err",
        shop_id="shop-err",
        started_at=None,
        served_by_staff_id=None,
        queue_notice_state=json.dumps({"eta": (NOW - timedelta(minutes=12)).isoformat()}),
    )
    asyncio.run(queue_ops.begin_service(None, booking, None, [], {}, NOW))
    assert booking.started_at == NOW
    assert value("alakh_queue_start_error_minutes_total", shop_id="shop-err") == pytest.approx(12)
    assert value("alakh_queue_starts_measured_total", shop_id="shop-err") == 1

    # Never told a time (served straight away): nothing to measure.
    untold = SimpleNamespace(**{**vars(booking), "id": "b-new", "queue_notice_state": None})
    asyncio.run(queue_ops.begin_service(None, untold, None, [], {}, NOW))
    assert value("alakh_queue_starts_measured_total", shop_id="shop-err") == 1


@pytest.mark.parametrize(
    ("transport", "outcome"),
    [
        (httpx.MockTransport(lambda r: httpx.Response(202)), "sent"),
        (httpx.MockTransport(lambda r: httpx.Response(422)), "rejected"),
        (httpx.MockTransport(lambda r: (_ for _ in ()).throw(httpx.ConnectError("down"))), "failed"),
    ],
)
@pytest.mark.asyncio
async def test_notifications_are_counted_by_outcome(transport, outcome):
    labels = {"event": "booking.queue_update", "outcome": outcome}
    before = value("alakh_booking_notifications_total", **labels)
    await Notifier("http://n", "key", transport).send("booking.queue_update", [{"user_id": "u"}], {})
    assert value("alakh_booking_notifications_total", **labels) == before + 1


@pytest.mark.asyncio
async def test_the_worker_times_each_pass(monkeypatch):
    calls = []

    async def one_pass(*args, **kwargs):
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError("stop")  # failed passes are timed but do not count as the last good one

    async def stop_after_two(_):
        if len(calls) == 2:
            raise asyncio.CancelledError

    monkeypatch.setattr(worker, "run_if_first", one_pass)
    monkeypatch.setattr(worker, "asyncio", SimpleNamespace(sleep=stop_after_two, CancelledError=asyncio.CancelledError))
    before = value("alakh_booking_worker_pass_seconds_count")
    with pytest.raises(asyncio.CancelledError):
        await worker.run_forever(None, None, None, None)
    assert value("alakh_booking_worker_pass_seconds_count") == before + 2
    assert value("alakh_booking_worker_last_pass_timestamp_seconds") > 0


@pytest.mark.asyncio
@pytest.mark.parametrize("free,runs", [(True, 1), (False, 0)])
async def test_only_one_process_does_a_worker_pass(monkeypatch, free, runs):
    done = []

    async def one_pass(*args, **kwargs):
        done.append(1)
        return {}

    class Guard:
        def get_bind(self):
            return SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

        async def execute(self, *args):
            return SimpleNamespace(scalar=lambda: free)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(worker, "run_once", one_pass)
    await worker.run_if_first(lambda: Guard())
    assert len(done) == runs
