#!/usr/bin/env python3
"""Load test for the live queue, through the API gateway, against a running stack (docs/LIVE_QUEUE.md §11).

    pip install httpx websockets
    python scripts/load/queue_load.py --make-admin-cmd "docker exec -i alakh_auth_service python -m app.cli make-admin {}"

What it does:
  1. sets up --shops approved shops, open all day, each with a service, 3 team members and --per-shop
     customers who join the line now (so every customer has a live place);
  2. for --duration seconds, every customer polls GET /bookings/{id}/queue every --interval seconds
     (start times spread over the interval), and each shop owner keeps /ws/shops/{id}/queue open;
  3. prints latency percentiles, errors and socket frames, and exits 1 when P95 is over --p95-ms or more
     than 1% of requests fail;
  4. cancels the bookings it made (unless --keep).

Each simulated customer sends its own X-Forwarded-For, so the gateway's per-client rate limits apply as
they do in production behind Caddy: run the gateway with TRUST_PROXY=1 (as docker-compose.prod.yml does).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import shlex
import statistics
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field

import httpx
import websockets

PASSWORD = "LoadPassw0rd!"


@dataclass
class Stats:
    # (seconds, status) per request; status 0 when it never got an answer.
    samples: list[tuple[float, int]] = field(default_factory=list)
    statuses: dict[int, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    frames: int = 0
    sockets_open: int = 0
    sockets_dropped: int = 0

    def record(self, seconds: float, status: int) -> None:
        self.samples.append((seconds, status))
        self.statuses[status] = self.statuses.get(status, 0) + 1


def pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(p / 100 * (len(ordered) - 1))))]


class Client:
    """One simulated person: their own forwarded address, so per-client limits count them separately."""

    def __init__(self, http: httpx.AsyncClient, n: int):
        self.http = http
        self.ip = f"10.{(n >> 16) & 255}.{(n >> 8) & 255}.{n & 255}"
        self.token: str | None = None

    async def call(self, method: str, path: str, body=None, ok=(200, 201)):
        headers = {"X-Forwarded-For": self.ip}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if method == "POST" and path == "/api/v1/bookings":
            headers["Idempotency-Key"] = uuid.uuid4().hex
        resp = await self.http.request(method, path, json=body, headers=headers)
        if resp.status_code not in ok:
            raise RuntimeError(f"{method} {path} -> {resp.status_code} {resp.text[:300]}")
        return resp.json() if resp.content else None

    async def sign_up(self, label: str, terms: str) -> tuple[str, str]:
        email = f"load-{label}-{uuid.uuid4().hex[:10]}@example.com"
        user = await self.call(
            "POST",
            "/api/v1/auth/register",
            {"email": email, "password": PASSWORD, "full_name": f"Load {label}", "accepted_terms_version": terms},
        )
        await self.sign_in(email)
        return user["id"], email

    async def sign_in(self, email: str) -> None:
        self.token = (await self.call("POST", "/api/v1/auth/login", {"email": email, "password": PASSWORD}))[
            "access_token"
        ]


async def set_up(
    http: httpx.AsyncClient, args
) -> tuple[list[Client], list[tuple[Client, str]], list[tuple[Client, str]]]:
    """Returns the owners with their shop ids and the customers with their booking ids."""
    counter = iter(range(1, 1_000_000))
    terms = (await http.get("/api/v1/legal/current")).json()["terms_version"]
    admin = Client(http, next(counter))
    _, admin_email = await admin.sign_up("admin", terms)
    subprocess.run(shlex.split(args.make_admin_cmd.format(admin_email)), check=True, capture_output=True)
    await admin.sign_in(admin_email)  # the role is in the new token

    async def one_shop(i: int):
        owner = Client(http, next(counter))
        owner_id, _ = await owner.sign_up(f"owner{i}", terms)
        shop = await owner.call(
            "POST",
            "/api/v1/shops",
            {
                "owner_id": owner_id,
                "name": f"Load Salon {i}",
                "category": "salon",
                "city": "Bengaluru",
                "address": f"{i} MG Road",
                "latitude": 12.975,
                "longitude": 77.605,
            },
        )
        if shop.get("verification_status") not in (None, "APPROVED"):
            await admin.call("POST", f"/api/v1/admin/shops/{shop['id']}/approve")
        week = [{"day": d, "intervals": [{"start": "00:00", "end": "24:00"}]} for d in range(7)]
        await owner.call("PUT", f"/api/v1/shops/{shop['id']}/hours", {"weekly": week})
        service = await owner.call(
            "POST",
            "/api/v1/services",
            {"shop_id": shop["id"], "name": "Haircut", "price_cents": 20000, "duration_minutes": 20},
        )
        for name in ("Asha", "Bilal", "Chitra"):
            await owner.call("POST", "/api/v1/staff", {"shop_id": shop["id"], "name": name})
        customers = []
        for j in range(args.per_shop):
            c = Client(http, next(counter))
            await c.sign_up(f"c{i}-{j}", terms)
            joined = await c.call("POST", "/api/v1/bookings/walk-in", {"service_id": service["id"]})
            customers.append((c, joined["booking_id"]))
        return (owner, shop["id"]), customers

    results = []
    # A few shops at a time: sign-ups hash passwords, which is the slow part.
    for start in range(0, args.shops, 4):
        results += await asyncio.gather(*(one_shop(i) for i in range(start, min(args.shops, start + 4))))
    owners = [r[0] for r in results]
    customers = [c for r in results for c in r[1]]
    return [admin], owners, customers


async def poll(customer: Client, booking_id: str, args, stats: Stats, stop: float) -> None:
    await asyncio.sleep(random.uniform(0, args.interval))
    while time.monotonic() < stop:
        started = time.perf_counter()
        try:
            resp = await customer.http.get(
                f"/api/v1/bookings/{booking_id}/queue",
                headers={"Authorization": f"Bearer {customer.token}", "X-Forwarded-For": customer.ip},
            )
            stats.record(time.perf_counter() - started, resp.status_code)
            if resp.status_code != 200 and len(stats.errors) < 10:
                stats.errors.append(f"{resp.status_code} {resp.text[:200]}")
        except httpx.HTTPError as e:
            stats.record(time.perf_counter() - started, 0)
            if len(stats.errors) < 10:
                stats.errors.append(f"{type(e).__name__}: {e}")
        await asyncio.sleep(args.interval)


async def watch(owner: Client, shop_id: str, args, stats: Stats, stop: float) -> None:
    url = f"{args.gateway.replace('http', 'ws', 1)}/api/v1/ws/shops/{shop_id}/queue?token={owner.token}"
    try:
        async with websockets.connect(url, open_timeout=10) as ws:
            stats.sockets_open += 1
            while time.monotonic() < stop:
                try:
                    frame = json.loads(await asyncio.wait_for(ws.recv(), timeout=max(0.1, stop - time.monotonic())))
                    if frame.get("type") == "queue":
                        stats.frames += 1
                except TimeoutError:
                    break
    except (OSError, websockets.WebSocketException) as e:
        stats.sockets_dropped += 1
        if len(stats.errors) < 10:
            stats.errors.append(f"socket {shop_id}: {type(e).__name__}: {e}")


async def main_async(args) -> int:
    limits = httpx.Limits(max_connections=args.connections, max_keepalive_connections=args.connections)
    async with httpx.AsyncClient(base_url=args.gateway, timeout=30, limits=limits) as http:
        t0 = time.monotonic()
        print(f"Setting up {args.shops} shops x {args.per_shop} customers ...", flush=True)
        _, owners, customers = await set_up(http, args)
        print(f"  ready in {time.monotonic() - t0:.0f}s: {len(customers)} customers in {len(owners)} lines", flush=True)

        stats = Stats()
        stop = time.monotonic() + args.duration
        print(f"Load: {len(customers)} customers every {args.interval:.0f}s for {args.duration:.0f}s, "
              f"{len(owners)} shop sockets", flush=True)  # fmt: skip
        await asyncio.gather(
            *(poll(c, b, args, stats, stop) for c, b in customers),
            *(watch(o, s, args, stats, stop) for o, s in owners),
        )

        ok = [seconds for seconds, code in stats.samples if code == 200]
        total = len(stats.samples)
        failed = total - stats.statuses.get(200, 0)
        p95 = pct(ok, 95) * 1000
        print("\nResults")
        print(f"  requests     {total} ({total / args.duration:.1f}/s), failed {failed} ({failed / max(total, 1):.2%})")
        print(f"  statuses     {dict(sorted(stats.statuses.items()))}")
        if ok:
            print(
                f"  latency ms   p50 {pct(ok, 50) * 1000:.0f}  p95 {p95:.0f}  p99 {pct(ok, 99) * 1000:.0f}  "
                f"max {max(ok) * 1000:.0f}  mean {statistics.mean(ok) * 1000:.0f}"
            )
        print(f"  sockets      {stats.sockets_open} open, {stats.sockets_dropped} failed, {stats.frames} queue frames")
        for e in stats.errors:
            print(f"  error        {e}")

        if not args.keep:
            # A few at a time, as customers leave a line; a timed-out cancel usually went through anyway.
            gate = asyncio.Semaphore(10)

            async def leave(c: Client, b: str) -> bool:
                async with gate:
                    try:
                        await c.call("POST", f"/api/v1/bookings/{b}/cancel", {"reason": "load test"}, ok=(200, 409))
                        return True
                    except (RuntimeError, httpx.HTTPError):
                        return False

            left = await asyncio.gather(*(leave(c, b) for c, b in customers))
            print(f"  cleaned up   cancelled {sum(left)} of {len(customers)} walk-ins", flush=True)

        passed = total > 0 and p95 <= args.p95_ms and failed / total <= 0.01 and stats.sockets_dropped == 0
        print(f"\nLOAD {'PASSED' if passed else 'FAILED'} (P95 target {args.p95_ms:.0f} ms, errors <= 1%)")
        return 0 if passed else 1


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--gateway", default="http://localhost:3000")
    parser.add_argument("--shops", type=int, default=20)
    parser.add_argument("--per-shop", type=int, default=10, help="customers in each shop's line")
    parser.add_argument("--interval", type=float, default=30, help="seconds between one customer's looks")
    parser.add_argument("--duration", type=float, default=180)
    parser.add_argument("--connections", type=int, default=100, help="HTTP connections to the gateway")
    parser.add_argument("--p95-ms", type=float, default=200)
    parser.add_argument("--keep", action="store_true", help="leave the walk-ins in the lines afterwards")
    parser.add_argument("--make-admin-cmd", required=True, help="command that makes {} (an email) an admin")
    return asyncio.run(main_async(parser.parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
