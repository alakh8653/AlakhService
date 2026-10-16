#!/usr/bin/env python3
"""Fill a local stack with demo data through the API gateway (run by `make db-seed`).

Creates, unless they already exist:
  * admin@example.com     - promoted to admin by `make db-seed` afterwards
  * owner@example.com     - owns "Demo Salon" (Pune) with three services
  * customer@example.com  - has one booking at Demo Salon tomorrow

Every account uses the password below. Running it again reuses what is already there.
It goes through the gateway rather than the databases, so the services validate
everything exactly as they do for the apps. Standard library only.

    python3 scripts/seed_database.py [--gateway http://localhost:3000/api/v1]
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlparse

PASSWORD = "Demo-pass-1"
ACCOUNTS = {
    "admin": ("admin@example.com", "Demo Admin"),
    "owner": ("owner@example.com", "Demo Owner"),
    "customer": ("customer@example.com", "Demo Customer"),
}
SHOP = {"name": "Demo Salon", "category": "salon", "city": "Pune", "address": "12 MG Road", "phone": "+919876543210"}
SERVICES = [
    {"name": "Haircut", "price_cents": 30000, "duration_minutes": 30},
    {"name": "Beard trim", "price_cents": 15000, "duration_minutes": 20},
    {"name": "Hair colour", "price_cents": 120000, "duration_minutes": 90},
]


class ApiError(Exception):
    def __init__(self, method, path, status, body):
        super().__init__(f"{method} {path} -> HTTP {status}: {body}")
        self.status = status


class Api:
    def __init__(self, base):
        self.base = base.rstrip("/")

    def call(self, method, path, body=None, token=None, query=None):
        url = self.base + path + (f"?{urlencode(query)}" if query else "")
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                raw = response.read()
        except urllib.error.HTTPError as e:
            raise ApiError(method, path, e.code, e.read().decode(errors="replace")[:300]) from None
        return json.loads(raw) if raw else None


def sign_in(api, role):
    """Registers the demo account if needed; returns (token, user id)."""
    email, name = ACCOUNTS[role]
    try:
        api.call("POST", "/auth/register", {"email": email, "password": PASSWORD, "full_name": name})
        print(f"  created {email}")
    except ApiError as e:
        if e.status not in (400, 409):
            raise
        print(f"  {email} already exists")
    try:
        token = api.call("POST", "/auth/login", {"email": email, "password": PASSWORD})["access_token"]
    except ApiError as e:
        sys.exit(f"Cannot sign in as {email} with the demo password ({e}). Was it registered with another password?")
    return token, api.call("GET", "/auth/me", token=token)["id"]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--gateway", default="http://localhost:3000/api/v1", help="API gateway base URL")
    parser.add_argument("--allow-remote", action="store_true", help="seed a gateway that is not on localhost")
    args = parser.parse_args()
    host = urlparse(args.gateway).hostname
    if host not in ("localhost", "127.0.0.1", "::1") and not args.allow_remote:
        sys.exit(
            f"Refusing to create demo accounts with a known password on {host}; pass --allow-remote to do it anyway."
        )

    api = Api(args.gateway)
    try:
        api.call("GET", "/shops", query={"limit": 1})
    except (urllib.error.URLError, ApiError) as e:
        sys.exit(f"The gateway at {args.gateway} is not answering ({e}). Start the stack first: make dev")

    print("Accounts:")
    sign_in(api, "admin")
    owner_token, owner_id = sign_in(api, "owner")
    customer_token, _ = sign_in(api, "customer")

    print("Shop:")
    shops = api.call("GET", "/shops", query={"owner_id": owner_id})
    if shops:
        shop = shops[0]
        print(f"  {shop['name']} already exists")
    else:
        shop = api.call("POST", "/shops", {"owner_id": owner_id, **SHOP}, token=owner_token)
        print(f"  created {shop['name']} ({shop['city']})")

    print("Services:")
    listed = api.call("GET", "/services", query={"shop_id": shop["id"], "include_inactive": "true", "limit": 200})
    services = {s["name"]: s for s in listed}
    for spec in SERVICES:
        if spec["name"] in services:
            print(f"  {spec['name']} already exists")
        else:
            services[spec["name"]] = api.call("POST", "/services", {"shop_id": shop["id"], **spec}, token=owner_token)
            print(f"  created {spec['name']} (Rs {spec['price_cents'] // 100})")

    print("Bookings:")
    mine = api.call("GET", "/bookings", token=customer_token)
    existing = mine.get("items", mine) if isinstance(mine, dict) else mine
    if existing:
        print(f"  customer already has {len(existing)} booking(s)")
    else:
        # Tomorrow 10:30 in India (05:00 UTC).
        when = (datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=5, minute=0, second=0, microsecond=0)
        booking = api.call(
            "POST",
            "/bookings",
            {"service_id": services["Haircut"]["id"], "scheduled_at": when.isoformat(), "notes": "Demo booking"},
            token=customer_token,
        )
        print(f"  created a Haircut booking for {when:%Y-%m-%d %H:%M} UTC ({booking['status']})")

    print(f"\nDone. Sign in with any account above and the password {PASSWORD!r}.")


if __name__ == "__main__":
    main()
