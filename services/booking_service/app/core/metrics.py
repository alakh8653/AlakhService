"""Prometheus metrics for the live queue, scraped from GET /metrics inside the server's network.

The gateway already measures every request per service; these say what it cannot see: how long the
queue's own pages take, whether the minute worker keeps up, whether queue messages reach
notification_service, and how far a customer's real start is from the time they were last told.
The alerts on them are in deploy/monitoring/prometheus/alerts.yml (group "live_queue").
"""

import time
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, Counter, Gauge, Histogram, generate_latest

QUEUE_REQUEST_SECONDS = Histogram(
    "alakh_queue_request_seconds",
    "Time to answer a live-queue request (the shop's day recomputed), by endpoint.",
    ["endpoint"],
    buckets=(0.025, 0.05, 0.1, 0.2, 0.3, 0.5, 1, 2, 5),
)
WORKER_PASS_SECONDS = Histogram(
    "alakh_booking_worker_pass_seconds",
    "Time one pass of the booking worker takes (reminders, queue notices, expiries, payment retries).",
    buckets=(0.1, 0.5, 1, 2, 5, 10, 20, 30, 60, 120),
)
WORKER_LAST_PASS = Gauge(
    "alakh_booking_worker_last_pass_timestamp_seconds",
    "When the booking worker last finished a pass without failing.",
)
NOTIFICATIONS = Counter(
    "alakh_booking_notifications_total",
    "Notifications handed to notification_service, by event and outcome (sent, rejected, failed).",
    ["event", "outcome"],
)
# Per shop, so an alert can name the shop whose listed lengths are far off: two series per shop.
START_ERROR_MINUTES = Counter(
    "alakh_queue_start_error_minutes_total",
    "Sum of |actual start - start last told to the customer|, in minutes, by shop.",
    ["shop_id"],
)
STARTS_MEASURED = Counter(
    "alakh_queue_starts_measured_total",
    "Services started whose customer had been told an expected start, by shop.",
    ["shop_id"],
)


def record_start(shop_id: Optional[str], told: Optional[datetime], started: datetime) -> Optional[float]:
    """Counts how far a start is from what the customer was last told; returns the error in minutes."""
    if not shop_id or told is None:
        return None
    error = abs((started - told).total_seconds()) / 60
    START_ERROR_MINUTES.labels(shop_id).inc(error)
    STARTS_MEASURED.labels(shop_id).inc()
    return error


# The queue's pages that recompute a shop's day, by the route they match.
TIMED_ROUTES = {
    "/api/v1/bookings/{booking_id}/queue": "customer",
    "/api/v1/bookings/shop/{shop_id}/queue": "shop_line",
    "/api/v1/bookings/shop/{shop_id}/queue/board": "board",
}


class QueueTimingMiddleware:
    """Times the requests that match TIMED_ROUTES (the router sets scope["route"] while routing)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method") != "GET":
            return await self.app(scope, receive, send)
        started = time.perf_counter()
        try:
            await self.app(scope, receive, send)
        finally:
            route = getattr(scope.get("route"), "path", None)
            if route in TIMED_ROUTES:
                QUEUE_REQUEST_SECONDS.labels(TIMED_ROUTES[route]).observe(time.perf_counter() - started)


def install_metrics(app: FastAPI) -> None:
    app.add_middleware(QueueTimingMiddleware)

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        """Not routed by the gateway; only Prometheus on the internal network reaches it."""
        return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)
