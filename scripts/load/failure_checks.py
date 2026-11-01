#!/usr/bin/env python3
"""Failure checks for the live queue against a running local stack (docs/LIVE_QUEUE.md §11).

    pip install httpx websockets
    python scripts/load/failure_checks.py --make-admin-cmd "docker exec -i alakh_auth_service python -m app.cli make-admin {}"

Sets up one shop with a team and a customer in its line, then, through the gateway:
  1. stops shop_service (docker stop) for longer than booking_service's caches, and checks that the
     customer's place, the shop's line, the public board and the shop's live socket still answer;
  2. stops Redis, and checks the same plus sign-in (the gateway's limits and sign-out checks fail open);
then starts each container again and waits until it is ready. Exit code 1 if any check fails. The
containers are started again even when a check fails or the script is interrupted.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import time

import httpx
import websockets
from queue_load import Client  # this folder is on the path when the script runs

failures: list[str] = []


def check(what: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'}  {what}{f' ({detail})' if detail else ''}", flush=True)
    if not ok:
        failures.append(what)


def docker(*args: str) -> None:
    subprocess.run(["docker", *args], check=True, capture_output=True)


async def wait_ready(http: httpx.AsyncClient, url: str, timeout: float = 90) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if (await http.get(url)).status_code == 200:
                return True
        except httpx.HTTPError:
            pass
        await asyncio.sleep(1)
    return False


async def socket_frame(args, shop_id: str, token: str) -> str:
    url = f"{args.gateway.replace('http', 'ws', 1)}/api/v1/ws/shops/{shop_id}/queue?token={token}"
    try:
        async with websockets.connect(url, open_timeout=10) as ws:
            kind = json.loads(await asyncio.wait_for(ws.recv(), 10)).get("type")
            return "frame" if kind == "queue" else f"a {kind} message"
    except websockets.exceptions.ConnectionClosed as e:
        return f"closed {e.rcvd.code if e.rcvd else '?'}"
    except (OSError, TimeoutError, websockets.WebSocketException) as e:
        return f"{type(e).__name__}"


async def looks(http, args, owner: Client, customer: Client, shop_id: str, booking_id: str, label: str) -> None:
    status = (await http.get(f"/api/v1/bookings/{booking_id}/queue", headers=customer_headers(customer))).status_code
    check(f"{label}: the customer sees their place", status == 200, str(status))
    status = (await http.get(f"/api/v1/bookings/shop/{shop_id}/queue", headers=customer_headers(owner))).status_code
    check(f"{label}: the shop sees its line", status == 200, str(status))
    status = (await http.get(f"/api/v1/bookings/shop/{shop_id}/queue/board")).status_code
    check(f"{label}: the board in the shop answers", status == 200, str(status))
    frame = await socket_frame(args, shop_id, owner.token or "")
    check(f"{label}: the shop's live socket sends the line", frame == "frame", frame)


def customer_headers(c: Client) -> dict:
    return {"Authorization": f"Bearer {c.token}", "X-Forwarded-For": c.ip}


async def main_async(args) -> int:
    async with httpx.AsyncClient(base_url=args.gateway, timeout=30) as http:
        print("Setting up a shop with a team and a customer in line", flush=True)
        terms = (await http.get("/api/v1/legal/current")).json()["terms_version"]
        admin = Client(http, 900_001)
        _, admin_email = await admin.sign_up("admin", terms)
        subprocess.run(args.make_admin_cmd.format(admin_email), shell=True, check=True, capture_output=True)
        await admin.sign_in(admin_email)
        owner = Client(http, 900_002)
        owner_id, _ = await owner.sign_up("owner", terms)
        shop = await owner.call(
            "POST",
            "/api/v1/shops",
            {"owner_id": owner_id, "name": "Failure Check Salon", "category": "salon", "city": "Bengaluru",
             "address": "1 MG Road", "latitude": 12.975, "longitude": 77.605},
        )  # fmt: skip
        if shop.get("verification_status") not in (None, "APPROVED"):
            await admin.call("POST", f"/api/v1/admin/shops/{shop['id']}/approve")
        week = [{"day": d, "intervals": [{"start": "00:00", "end": "24:00"}]} for d in range(7)]
        await owner.call("PUT", f"/api/v1/shops/{shop['id']}/hours", {"weekly": week})
        service = await owner.call(
            "POST",
            "/api/v1/services",
            {"shop_id": shop["id"], "name": "Haircut", "price_cents": 20000, "duration_minutes": 20},
        )
        for name in ("Asha", "Bilal"):
            await owner.call("POST", "/api/v1/staff", {"shop_id": shop["id"], "name": name})
        customer = Client(http, 900_003)
        customer_email = (await customer.sign_up("customer", terms))[1]
        booking_id = (await customer.call("POST", "/api/v1/bookings/walk-in", {"service_id": service["id"]}))[
            "booking_id"
        ]
        await looks(http, args, owner, customer, shop["id"], booking_id, "all up")

        print(f"shop_service stopped (waiting {args.cache_wait:.0f}s, past booking_service's caches)", flush=True)
        docker("stop", args.shop_container)
        try:
            await asyncio.sleep(args.cache_wait)
            await looks(http, args, owner, customer, shop["id"], booking_id, "shop_service down")
        finally:
            docker("start", args.shop_container)
        check("shop_service is back", await wait_ready(http, f"http://127.0.0.1:{args.shop_port}/ready"))

        print("Redis stopped", flush=True)
        docker("stop", args.redis_container)
        try:
            await asyncio.sleep(3)
            await looks(http, args, owner, customer, shop["id"], booking_id, "Redis down")
            status = (
                await http.post(
                    "/api/v1/auth/login",
                    json={"email": customer_email, "password": "LoadPassw0rd!"},
                    headers={"X-Forwarded-For": customer.ip},
                )
            ).status_code
            check("Redis down: signing in still works", status == 200, str(status))
        finally:
            docker("start", args.redis_container)
        await asyncio.sleep(3)
        check("Redis is back: the gateway answers", (await http.get("/health")).status_code == 200)

        await customer.call("POST", f"/api/v1/bookings/{booking_id}/cancel", {"reason": "failure check"}, ok=(200, 409))
    print(f"\nFAILURE CHECKS {'PASSED' if not failures else 'FAILED: ' + '; '.join(failures)}")
    return 1 if failures else 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--gateway", default="http://localhost:3000")
    parser.add_argument("--make-admin-cmd", required=True)
    parser.add_argument("--shop-container", default="alakh_shop_service")
    parser.add_argument("--shop-port", type=int, default=8003)
    parser.add_argument("--redis-container", default="alakh_redis")
    parser.add_argument("--cache-wait", type=float, default=40, help="seconds shop_service stays down first")
    return asyncio.run(main_async(parser.parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
