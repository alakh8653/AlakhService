#!/usr/bin/env python3
"""End-to-end smoke flow through the API gateway, against a running stack (docker compose).

    python3 scripts/e2e/flow.py                                  # http://localhost:3000
    python3 scripts/e2e/flow.py --gateway http://localhost:3000 --make-admin-cmd \\
        "docker compose exec -T auth_service python -m app.cli make-admin {}"

What it does (exit code 1 on the first hard failure):
  1. every service's /health (and the gateway's) answers
  2. sign-up needs the Terms (422 without accepted_terms_version); GET /legal/current works
  3. a shop owner signs up, opens a shop and lists a service
  4. a customer signs up and books it; the owner confirms, starts and completes it
  5. payments (soft): cash payment, cash received, earnings and invoice. Steps whose endpoint is not
     there yet (404/405/501) are reported as SKIPPED, not failures.

Standard library only, so it runs on any runner with Python 3.9+.
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone

PASSWORD = "E2ePassw0rd!"

# Published by docker-compose.yml on 127.0.0.1 (name -> port).
SERVICES = {
    "auth_service": 8001,
    "user_service": 8002,
    "shop_service": 8003,
    "booking_service": 8004,
    "payment_service": 8005,
    "notification_service": 8006,
    "tracking_service": 8007,
    "queue_service": 8008,
    "analytics_service": 8010,
    "dispute_service": 8011,
    "trust_risk_service": 8012,
    "admin_service": 8013,
    "compliance_service": 8014,
    "pricing_engine": 8015,
    "service_catalog_service": 8016,
}

SKIPPABLE = (404, 405, 501)


class Failure(Exception):
    pass


class Api:
    def __init__(self, base: str):
        self.base = base.rstrip("/")

    def call(self, method: str, path: str, body=None, token: str | None = None, headers: dict | None = None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
        req.add_header("Accept", "application/json")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - URLs from the command line
                raw = resp.read()
                status = resp.status
                content_type = resp.headers.get("content-type", "")
        except urllib.error.HTTPError as e:
            raw, status, content_type = e.read(), e.code, e.headers.get("content-type", "")
        if "json" in content_type and raw:
            try:
                return status, json.loads(raw)
            except ValueError:
                pass
        return status, raw.decode(errors="replace")

    def expect(self, what: str, method: str, path: str, codes=(200, 201), **kw):
        status, body = self.call(method, path, **kw)
        if status not in codes:
            raise Failure(f"{what}: {method} {path} -> {status} {str(body)[:300]}")
        print(f"  ok    {what} ({status})")
        return body

    def soft(self, what: str, method: str, path: str, codes=(200, 201), **kw):
        """A step that depends on work not merged yet: missing endpoints are skipped, not failed."""
        status, body = self.call(method, path, **kw)
        if status in SKIPPABLE and status not in codes:
            print(f"  SKIP  {what}: {method} {path} -> {status} (endpoint not available yet)")
            return None
        if status not in codes:
            raise Failure(f"{what}: {method} {path} -> {status} {str(body)[:300]}")
        print(f"  ok    {what} ({status})")
        return body


def wait_healthy(urls: dict[str, str], timeout: float) -> None:
    print("Health")
    deadline = time.monotonic() + timeout
    pending = dict(urls)
    while pending and time.monotonic() < deadline:
        for name, url in list(pending.items()):
            try:
                with urllib.request.urlopen(url, timeout=5) as resp:  # noqa: S310
                    if resp.status == 200:
                        print(f"  ok    {name}")
                        del pending[name]
            except (urllib.error.URLError, OSError):
                pass
        if pending:
            time.sleep(2)
    if pending:
        raise Failure(f"not healthy after {timeout:.0f}s: {', '.join(sorted(pending))}")


def sign_up(api: Api, label: str, terms: str) -> tuple[str, str, str]:
    email = f"e2e-{label}-{uuid.uuid4().hex[:10]}@example.com"
    user = api.expect(
        f"{label} signs up",
        "POST",
        "/api/v1/auth/register",
        body={
            "email": email,
            "password": PASSWORD,
            "full_name": f"E2E {label.title()}",
            "accepted_terms_version": terms,
        },
        codes=(201,),
    )
    if user.get("accepted_terms_version") != terms:
        raise Failure(f"{label}: the accepted terms version was not stored: {user}")
    token = sign_in(api, label, email)
    return user["id"], email, token


def sign_in(api: Api, label: str, email: str) -> str:
    return api.expect(f"{label} signs in", "POST", "/api/v1/auth/login", body={"email": email, "password": PASSWORD})[
        "access_token"
    ]


def approve_shop(api: Api, shop: dict, make_admin_cmd: str | None, terms: str) -> None:
    """New shops may wait for admin review (verification_status); approve it so customers can book."""
    status = shop.get("verification_status")
    if status in (None, "APPROVED"):
        return
    if not make_admin_cmd:
        print(f"  SKIP  shop is {status} and no --make-admin-cmd was given to approve it")
        return
    _, admin_email, _ = sign_up(api, "admin", terms)
    subprocess.run(shlex.split(make_admin_cmd.format(admin_email)), check=True, capture_output=True)
    admin = sign_in(api, "admin", admin_email)  # signs in again: the role is in the token
    api.expect("admin sees it in the review queue", "GET", "/api/v1/admin/shops/review-queue", token=admin)
    approved = api.expect("admin approves the shop", "POST", f"/api/v1/admin/shops/{shop['id']}/approve", token=admin)
    if approved.get("verification_status") != "APPROVED":
        raise Failure(f"shop was not approved: {approved}")


def run(api: Api, args) -> None:
    gateway = args.gateway.rstrip("/")
    urls = {"api_gateway": f"{gateway}/health"}
    if not args.skip_service_health:
        urls.update({name: f"http://{args.service_host}:{port}/health" for name, port in SERVICES.items()})
    wait_healthy(urls, args.timeout)

    print("Terms and legal links")
    legal = api.expect("legal links are public", "GET", "/api/v1/legal/current")
    terms = legal["terms_version"]
    for key in ("privacy_url", "terms_url", "refund_url", "grievance_url"):
        if not str(legal.get(key, "")).startswith("http"):
            raise Failure(f"/legal/current has no {key}: {legal}")
    status, body = api.call(
        "POST",
        "/api/v1/auth/register",
        body={
            "email": f"e2e-noterms-{uuid.uuid4().hex[:8]}@example.com",
            "password": PASSWORD,
            "full_name": "No Terms",
        },
    )
    if status != 422 or "Terms" not in str(body):
        raise Failure(f"sign-up without accepting the terms should be 422, got {status} {body}")
    print("  ok    sign-up without the terms is refused (422)")

    print("Shop owner")
    owner_id, _, owner = sign_up(api, "owner", terms)
    shop = api.expect(
        "owner opens a shop",
        "POST",
        "/api/v1/shops",
        token=owner,
        body={
            "owner_id": owner_id,
            "name": "E2E Salon",
            "category": "salon",
            "city": "Bengaluru",
            "address": "1 MG Road",
            "latitude": 12.975,
            "longitude": 77.605,
        },
        codes=(201,),
    )
    approve_shop(api, shop, args.make_admin_cmd, terms)
    service = api.expect(
        "owner lists a service",
        "POST",
        "/api/v1/services",
        token=owner,
        body={"shop_id": shop["id"], "name": "Haircut", "price_cents": 29900, "duration_minutes": 30},
        codes=(201,),
    )
    api.expect("the service can be browsed without an account", "GET", f"/api/v1/services/{service['id']}")

    print("Customer booking")
    _, _, customer = sign_up(api, "customer", terms)
    when = (datetime.now(timezone.utc) + timedelta(days=2)).replace(hour=6, minute=0, second=0, microsecond=0)
    booking = api.expect(
        "customer books the service",
        "POST",
        "/api/v1/bookings",
        token=customer,
        headers={"Idempotency-Key": uuid.uuid4().hex},
        body={"service_id": service["id"], "scheduled_at": when.isoformat()},
        codes=(201,),
    )
    if booking.get("total_amount") != 29900 or booking.get("shop_id") != shop["id"]:
        raise Failure(f"booking was not priced from the catalogue: {booking}")
    bid = booking["id"]
    api.expect("owner confirms", "PUT", f"/api/v1/bookings/{bid}/status", token=owner, body={"status": "CONFIRMED"})

    print("Payment (cash; online payments need Razorpay keys)")
    payment = api.soft(
        "customer chooses to pay cash",
        "POST",
        "/api/v1/payments/initiate",
        token=customer,
        body={"booking_id": bid, "payment_method": "cash", "idempotency_key": uuid.uuid4().hex},
        codes=(201,),
    )

    print("Service")
    api.expect("owner starts", "PUT", f"/api/v1/bookings/{bid}/status", token=owner, body={"status": "IN_PROGRESS"})
    done = api.expect(
        "owner completes", "PUT", f"/api/v1/bookings/{bid}/status", token=owner, body={"status": "COMPLETED"}
    )
    if done.get("status") != "COMPLETED":
        raise Failure(f"booking did not complete: {done}")
    seen = api.expect("customer sees it completed", "GET", f"/api/v1/bookings/{bid}", token=customer)
    if seen.get("status") != "COMPLETED":
        raise Failure(f"customer sees {seen.get('status')}")

    print("Payment settlement and earnings")
    if payment:
        api.expect("owner confirms the cash", "POST", f"/api/v1/payments/{payment['id']}/cash-received", token=owner)
        api.expect("invoice", "GET", f"/api/v1/payments/{payment['id']}/invoice", token=customer)
    today = datetime.now(timezone.utc).date()
    earnings = api.expect(
        "shop earnings",
        "GET",
        f"/api/v1/payments/shops/{shop['id']}/earnings?from={today - timedelta(days=1)}&to={today + timedelta(days=3)}",
        token=owner,
    )
    if earnings.get("currency") != "INR":
        raise Failure(f"earnings response is not in INR: {earnings}")
    api.expect("shop payouts", "GET", f"/api/v1/payments/shops/{shop['id']}/payouts", token=owner)

    print("Notifications")
    api.expect("customer's notifications list", "GET", "/api/v1/notifications/me", token=customer)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--gateway", default="http://localhost:3000")
    parser.add_argument("--service-host", default="127.0.0.1", help="where the services' ports are published")
    parser.add_argument("--skip-service-health", action="store_true", help="check only the gateway's /health")
    parser.add_argument("--timeout", type=float, default=240, help="seconds to wait for everything to be healthy")
    parser.add_argument(
        "--make-admin-cmd",
        help="command that makes {} (an email) an admin, used to approve the test shop if shops need review",
    )
    args = parser.parse_args(argv)
    started = time.monotonic()
    try:
        run(Api(args.gateway), args)
    except Failure as e:
        print(f"\nE2E FAILED: {e}")
        return 1
    print(f"\nE2E PASSED in {time.monotonic() - started:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
