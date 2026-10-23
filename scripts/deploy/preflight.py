#!/usr/bin/env python3
"""Checks a filled-in .env.production (and this server) before AlakhService is deployed.

    python3 scripts/deploy/preflight.py                      # .env.production + this server
    python3 scripts/deploy/preflight.py --env-file other.env
    python3 scripts/deploy/preflight.py --no-system          # only the file (CI, laptops)
    python3 scripts/deploy/preflight.py --strict             # warnings fail too

Exit code 0 = safe to deploy (warnings are printed but allowed), 1 = fix the errors first,
2 = bad usage. Standard library only, so it runs on a fresh server with nothing installed.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import urllib.request
from pathlib import Path

# Secrets the services refuse in production (services/*/app/config.py, api_gateway/src/config.ts),
# plus the markers used in .env.production.example.
PLACEHOLDER_MARKERS = (
    "replace_me",
    "replace-me",
    "changeme",
    "change-me",
    "change_me",
    "change-in-production",
    "your-secret",
    "your_secret",
    "your-",
    "example.com",
    "xxxx",
    "<",
    ">",
)
SECRET_MIN_LENGTH = {
    "JWT_SECRET_KEY": 32,
    "INTERNAL_API_KEY": 32,
    "METRICS_TOKEN": 32,
    "POSTGRES_PASSWORD": 16,
}
REQUIRED = [
    "DOMAIN",
    "ACME_EMAIL",
    "JWT_SECRET_KEY",
    "INTERNAL_API_KEY",
    "METRICS_TOKEN",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "CORS_ORIGINS",
    "PASSWORD_RESET_URL",
]
HOSTNAME = re.compile(r"^(?=.{4,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_COMPOSE = (2, 24)  # `!reset` in docker-compose.prod.yml


class Report:
    def __init__(self, color: bool):
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.color = color

    def _print(self, mark: str, code: str, message: str) -> None:
        if self.color:
            mark = f"\033[{code}m{mark}\033[0m"
        print(f"  {mark} {message}")

    def ok(self, message: str) -> None:
        self._print("ok  ", "32", message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)
        self._print("WARN", "33", message)

    def error(self, message: str) -> None:
        self.errors.append(message)
        self._print("FAIL", "31", message)

    def section(self, title: str) -> None:
        print(f"\n{title}")


def parse_env_file(path: Path) -> tuple[dict[str, str], list[str]]:
    """KEY=value lines as Docker Compose reads them (comments, blank lines, optional quotes)."""
    values: dict[str, str] = {}
    problems: list[str] = []
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        if "=" not in line:
            problems.append(f"line {number}: expected KEY=value, got {raw.strip()[:40]!r}")
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            problems.append(f"line {number}: {key!r} is not a valid variable name")
            continue
        if raw.split("=", 1)[0] != raw.split("=", 1)[0].rstrip():
            problems.append(f"line {number}: remove the space before '=' in {key}")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()  # inline comment
        if key in values:
            problems.append(f"line {number}: {key} is set twice (the last one wins); keep one")
        values[key] = value
    return values, problems


def looks_like_placeholder(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def check_file(env: dict[str, str], r: Report) -> None:
    r.section("Required settings")
    for key in REQUIRED:
        value = env.get(key, "")
        if not value:
            r.error(f"{key} is missing or empty")
        elif looks_like_placeholder(value):
            r.error(f"{key} still holds a placeholder ({value[:30]!r}); fill in the real value")
        else:
            r.ok(f"{key} is set")

    for key, value in env.items():
        if "$" in value:
            r.error(f"{key} contains '$': Docker Compose would treat it as a variable; generate a new value")

    r.section("Secrets")
    for key, minimum in SECRET_MIN_LENGTH.items():
        value = env.get(key, "")
        if not value or looks_like_placeholder(value):
            continue  # already reported above
        if len(value) < minimum:
            r.error(f"{key} is {len(value)} characters; it needs at least {minimum} (openssl rand -hex 32)")
        elif "change" in value.lower():
            r.error(f"{key} contains 'change', which the services reject; generate a random value")
        elif len(set(value)) < 8:
            r.error(f"{key} is not random enough; generate one with openssl rand -hex 32")
        else:
            r.ok(f"{key} is {len(value)} characters")
    secrets = [env.get(k, "") for k in ("JWT_SECRET_KEY", "INTERNAL_API_KEY", "METRICS_TOKEN")]
    real_secrets = all(secrets) and not any(looks_like_placeholder(v) for v in secrets)
    if real_secrets and len(set(secrets)) < len(secrets):
        r.error("JWT_SECRET_KEY, INTERNAL_API_KEY and METRICS_TOKEN must all be different values")
    password = env.get("POSTGRES_PASSWORD", "")
    if password and not re.fullmatch(r"[A-Za-z0-9._~-]+", password):
        r.error("POSTGRES_PASSWORD may only use letters, digits and . _ ~ - (it is placed inside a URL)")
    user = env.get("POSTGRES_USER", "")
    if user and not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", user):
        r.error("POSTGRES_USER should be lower-case letters, digits and underscores")

    r.section("Domain, HTTPS and browser access")
    domain = env.get("DOMAIN", "").strip().lower()
    if domain and not looks_like_placeholder(domain):
        if domain.startswith(("http://", "https://")) or "/" in domain:
            r.error("DOMAIN must be a bare domain like alakhservice.in (no https://, no slashes)")
        elif domain.startswith("www."):
            r.error("DOMAIN must not start with www.; use the bare domain (api./shop./admin. are added)")
        elif not HOSTNAME.match(domain):
            r.error(f"DOMAIN {domain!r} is not a valid domain name")
        else:
            r.ok(f"sites: https://api.{domain}  https://shop.{domain}  https://admin.{domain}")
    if not HOSTNAME.match(domain) or looks_like_placeholder(domain):
        domain = ""  # checks that compare against the domain are skipped until it is valid
    email = env.get("ACME_EMAIL", "")
    if email and not looks_like_placeholder(email) and not EMAIL.match(email):
        r.error(f"ACME_EMAIL {email!r} is not an email address")

    origins = [o.strip() for o in env.get("CORS_ORIGINS", "").split(",") if o.strip()]
    if origins and not looks_like_placeholder(env.get("CORS_ORIGINS", "")):
        expected = {f"https://shop.{domain}", f"https://admin.{domain}"} if domain else set()
        bad = False
        for origin in origins:
            if origin == "*":
                r.error("CORS_ORIGINS must not be *; list the two dashboard origins")
                bad = True
            elif not origin.startswith("https://"):
                r.error(f"CORS origin {origin!r} must start with https://")
                bad = True
            elif origin.endswith("/"):
                r.error(f"CORS origin {origin!r} must not end with '/' (browsers send no trailing slash)")
                bad = True
            elif "localhost" in origin or "127.0.0.1" in origin:
                r.error(f"CORS origin {origin!r} is a local address; remove it in production")
                bad = True
            elif expected and origin not in expected:
                r.warn(f"CORS origin {origin!r} is not one of the dashboards on {domain}")
        missing = expected - set(origins)
        if missing:
            r.error(f"CORS_ORIGINS is missing {', '.join(sorted(missing))} (the dashboards would be blocked)")
        elif not bad:
            r.ok("CORS_ORIGINS lists both dashboards")

    reset_url = env.get("PASSWORD_RESET_URL", "")
    if reset_url and not looks_like_placeholder(reset_url):
        if not reset_url.startswith("https://"):
            r.error("PASSWORD_RESET_URL must start with https://")
        elif domain and not reset_url.startswith(f"https://shop.{domain}/"):
            r.warn(f"PASSWORD_RESET_URL does not point at https://shop.{domain}/reset-password")
        else:
            r.ok("PASSWORD_RESET_URL points at the shop dashboard")

    allowed = env.get("ADMIN_ALLOWED_IPS", "").split()
    if allowed:
        everyone = True
        for item in allowed:
            try:
                net = ipaddress.ip_network(item, strict=False)
                if net.prefixlen != 0:
                    everyone = False
            except ValueError:
                r.error(f"ADMIN_ALLOWED_IPS: {item!r} is not an IP address or CIDR range")
        if everyone:
            r.warn(
                "ADMIN_ALLOWED_IPS lets every IP reach the admin dashboard (login still applies); "
                "consider limiting it to your office/home IP"
            )
        else:
            r.ok(f"admin dashboard limited to {' '.join(allowed)}")

    check_integrations(env, r)
    check_backups_and_monitoring(env, r)


def check_integrations(env: dict[str, str], r: Report) -> None:
    r.section("Payments (Razorpay)")
    keys = ("RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET", "RAZORPAY_WEBHOOK_SECRET")
    present = [k for k in keys if env.get(k)]
    if not present:
        r.warn("Razorpay is not configured: customers can only pay cash")
    elif len(present) < len(keys):
        missing = [k for k in keys if not env.get(k)]
        r.error(f"Razorpay is half configured; also set {', '.join(missing)}")
    else:
        key_id = env["RAZORPAY_KEY_ID"]
        for k in keys:
            if looks_like_placeholder(env[k]):
                r.error(f"{k} still holds a placeholder")
        if key_id.startswith("rzp_live_"):
            r.ok("Razorpay LIVE keys: real payments are on")
        elif key_id.startswith("rzp_test_"):
            r.warn("Razorpay TEST keys (rzp_test_): no real money moves; switch to rzp_live_ keys to go live")
        else:
            r.error("RAZORPAY_KEY_ID should start with rzp_live_ (or rzp_test_)")
        if len(env["RAZORPAY_WEBHOOK_SECRET"]) < 16:
            r.warn("RAZORPAY_WEBHOOK_SECRET is short; use openssl rand -hex 24")
        domain = env.get("DOMAIN", "<DOMAIN>")
        r.ok(f"Razorpay webhook URL to set: https://api.{domain}/api/v1/webhooks/razorpay")

    r.section("SMS, email and push")
    twilio = ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM_NUMBER")
    present = [k for k in twilio if env.get(k)]
    if not present:
        r.warn("Twilio is not configured: one-time sign-in codes will NOT be sent by SMS")
    elif len(present) < len(twilio):
        r.error(f"Twilio is half configured; also set {', '.join(k for k in twilio if not env.get(k))}")
    else:
        if not env["TWILIO_ACCOUNT_SID"].startswith("AC"):
            r.error("TWILIO_ACCOUNT_SID should start with AC")
        if not env["TWILIO_FROM_NUMBER"].startswith("+") and not env["TWILIO_FROM_NUMBER"].isalnum():
            r.warn("TWILIO_FROM_NUMBER should be in international format, e.g. +1XXXXXXXXXX")
        r.ok("Twilio SMS configured (Indian numbers need DLT registration; see docs/DEPLOYMENT.md)")

    if not env.get("SMTP_HOST"):
        r.warn("SMTP_HOST is empty: password-reset emails will NOT be sent")
    else:
        errors_before = len(r.errors)
        for k in ("SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM_EMAIL"):
            if not env.get(k):
                r.error(f"SMTP_HOST is set but {k} is empty")
        if env.get("SMTP_PORT", "587") == "465":
            r.error("SMTP_PORT 465 (implicit TLS) is not supported; use 587 (STARTTLS)")
        if env.get("SMTP_FROM_EMAIL") and not EMAIL.match(env["SMTP_FROM_EMAIL"]):
            r.error("SMTP_FROM_EMAIL is not an email address")
        if len(r.errors) == errors_before:
            r.ok(f"email via {env['SMTP_HOST']}")

    provider = (env.get("CALL_PROVIDER") or "none").strip().lower()
    exotel = ("EXOTEL_API_KEY", "EXOTEL_API_TOKEN", "EXOTEL_ACCOUNT_SID", "EXOTEL_CALLER_ID")
    if provider == "exotel":
        missing = [k for k in exotel if not env.get(k)]
        if missing:
            r.error(f"CALL_PROVIDER=exotel but {', '.join(missing)} empty: calling would stay off")
        else:
            r.ok(f"masked calls via Exotel from {env['EXOTEL_CALLER_ID']}")
    elif provider not in ("", "none"):
        r.error(f"CALL_PROVIDER must be none or exotel, not {provider}")
    else:
        r.ok("masked calls off: customers and shops talk through the in-app chat only")

    fcm = env.get("FCM_SERVICE_ACCOUNT_JSON", "")
    if not fcm:
        r.warn("FCM_SERVICE_ACCOUNT_JSON is empty: no push notifications to the mobile app")
    else:
        try:
            parsed = json.loads(fcm)
            if parsed.get("type") != "service_account" or "private_key" not in parsed:
                r.error("FCM_SERVICE_ACCOUNT_JSON is JSON but not a Firebase service-account key")
            else:
                r.ok(f"push notifications for Firebase project {parsed.get('project_id', '?')}")
        except (ValueError, AttributeError):
            r.error("FCM_SERVICE_ACCOUNT_JSON is not valid one-line JSON (see the command in the example file)")

    for flag in ("LOG_OTP_CODES", "LOG_PASSWORD_RESET_TOKENS"):
        if env.get(flag, "").lower() in ("1", "true", "yes"):
            r.error(f"{flag} must not be on in production (it writes secrets to the logs)")


def check_backups_and_monitoring(env: dict[str, str], r: Report) -> None:
    r.section("Backups and monitoring")
    for key, default in (("BACKUP_INTERVAL_HOURS", "24"), ("BACKUP_KEEP_DAYS", "14"), ("BACKUP_MIN_KEEP", "3")):
        value = env.get(key, default) or default
        if not value.isdigit() or int(value) < 1:
            r.error(f"{key} must be a whole number of at least 1, got {value!r}")
    if env.get("OFFSITE_RCLONE_REMOTE"):
        r.ok(f"off-site backups to {env['OFFSITE_RCLONE_REMOTE']} (schedule scripts/deploy/offsite-backup.sh in cron)")
    else:
        r.warn("OFFSITE_RCLONE_REMOTE is empty: backups stay on this server's disk only")

    profiles = [p.strip() for p in env.get("COMPOSE_PROFILES", "").split(",") if p.strip()]
    if "monitoring" in profiles:
        errors_before = len(r.errors)
        password = env.get("GRAFANA_ADMIN_PASSWORD", "")
        if len(password) < 12 or looks_like_placeholder(password):
            r.error("monitoring is on: set GRAFANA_ADMIN_PASSWORD (12+ characters; openssl rand -hex 16)")
        if not env.get("ALERT_EMAIL_TO") and not (env.get("TELEGRAM_BOT_TOKEN") and env.get("TELEGRAM_CHAT_ID")):
            r.warn("monitoring is on but no ALERT_EMAIL_TO or TELEGRAM_*: alerts only show in Grafana")
        if env.get("ALERT_EMAIL_TO") and not env.get("SMTP_HOST"):
            r.error("ALERT_EMAIL_TO needs the SMTP_* settings to send mail")
        if bool(env.get("TELEGRAM_BOT_TOKEN")) != bool(env.get("TELEGRAM_CHAT_ID")):
            r.error("set both TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID, or neither")
        if env.get("TELEGRAM_CHAT_ID") and not re.fullmatch(r"-?\d+", env["TELEGRAM_CHAT_ID"]):
            r.error("TELEGRAM_CHAT_ID must be a number (e.g. 123456789 or -100123456789)")
        if len(r.errors) == errors_before:
            r.ok("monitoring profile on (Grafana on 127.0.0.1:3001 via SSH tunnel)")
    else:
        r.warn("monitoring is off (COMPOSE_PROFILES=monitoring turns on Prometheus, alerts and Grafana)")


# ---------------------------------------------------------------------------
# This server
# ---------------------------------------------------------------------------


def run(cmd: list[str]) -> str | None:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=20, check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def public_ip() -> str | None:
    for url in ("https://api.ipify.org", "https://ifconfig.me/ip", "https://checkip.amazonaws.com"):
        try:
            with urllib.request.urlopen(url, timeout=4) as response:  # noqa: S310 - fixed https URLs
                text = response.read().decode().strip()
                ipaddress.ip_address(text)
                return text
        except (OSError, ValueError):
            continue
    return None


def check_system(env: dict[str, str], repo: Path, r: Report) -> None:
    r.section("This server")
    if shutil.which("docker") is None:
        r.error("Docker is not installed (see docs/DEPLOYMENT.md, step 3)")
    else:
        version = run(["docker", "version", "--format", "{{.Server.Version}}"])
        if version is None:
            r.error("cannot talk to the Docker daemon: is it running, and is your user in the docker group?")
        else:
            r.ok(f"Docker Engine {version}")
        compose = run(["docker", "compose", "version", "--short"])
        match = re.match(r"v?(\d+)\.(\d+)", compose or "")
        if not match:
            r.error("Docker Compose v2 is missing (install the docker-compose-plugin package)")
        elif (int(match.group(1)), int(match.group(2))) < MIN_COMPOSE:
            r.error(f"Docker Compose {compose} is too old; {MIN_COMPOSE[0]}.{MIN_COMPOSE[1]}+ is needed")
        else:
            r.ok(f"Docker Compose {compose}")

    usage = shutil.disk_usage(repo)
    free_gb = usage.free / 1e9
    if free_gb < 5:
        r.error(f"only {free_gb:.1f} GB free on disk; at least 10 GB is needed for images and backups")
    elif free_gb < 15:
        r.warn(f"{free_gb:.1f} GB free on disk; 20 GB+ is comfortable")
    else:
        r.ok(f"{free_gb:.0f} GB free on disk")

    try:
        meminfo = Path("/proc/meminfo").read_text()
        total_gb = int(re.search(r"MemTotal:\s+(\d+)", meminfo).group(1)) / 1e6
        if total_gb < 3.5:
            r.error(f"{total_gb:.1f} GB of memory; the stack needs 4 GB minimum (8 GB recommended)")
        elif total_gb < 7:
            r.warn(f"{total_gb:.1f} GB of memory; it fits, but 8 GB is recommended (add swap if builds fail)")
        else:
            r.ok(f"{total_gb:.1f} GB of memory")
    except (OSError, AttributeError):
        r.warn("could not read /proc/meminfo")

    domain = env.get("DOMAIN", "")
    if not domain or looks_like_placeholder(domain):
        return
    my_ip = public_ip()
    for name in (f"api.{domain}", f"shop.{domain}", f"admin.{domain}"):
        try:
            addresses = sorted({info[4][0] for info in socket.getaddrinfo(name, 443, proto=socket.IPPROTO_TCP)})
        except socket.gaierror:
            r.warn(
                f"{name} does not resolve yet: create an A record pointing at this server "
                "(HTTPS certificates cannot be issued until it does)"
            )
            continue
        if my_ip and my_ip not in addresses:
            r.warn(
                f"{name} resolves to {', '.join(addresses)}, but this server's public IP is {my_ip} "
                "(fine only if a proxy/CDN is in front; see docs/DEPLOYMENT.md)"
            )
        else:
            r.ok(f"{name} -> {', '.join(addresses)}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--env-file", default=".env.production", help="file to check (default: .env.production)")
    parser.add_argument("--no-system", action="store_true", help="skip Docker/disk/memory/DNS checks")
    parser.add_argument("--strict", action="store_true", help="treat warnings as errors")
    args = parser.parse_args(argv)

    repo = Path(__file__).resolve().parents[2]
    path = Path(args.env_file)
    if not path.is_absolute() and not path.exists():
        path = repo / path
    color = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
    r = Report(color)

    print(f"AlakhService preflight: {path}")
    if not path.is_file():
        r.error(f"{path} not found. Create it: cp .env.production.example .env.production")
        return 1
    mode = path.stat().st_mode & 0o777
    env, problems = parse_env_file(path)
    r.section("File")
    for problem in problems:
        r.error(problem)
    if mode & 0o077:
        r.warn(f"{path.name} is readable by other users (mode {mode:o}); run: chmod 600 {path.name}")
    if not problems:
        r.ok(f"{len(env)} settings read")

    check_file(env, r)
    if not args.no_system:
        check_system(env, repo, r)

    print()
    if r.errors:
        print(f"PREFLIGHT FAILED: {len(r.errors)} error(s), {len(r.warnings)} warning(s). Fix the FAIL lines above.")
        return 1
    if r.warnings and args.strict:
        print(f"PREFLIGHT FAILED (--strict): {len(r.warnings)} warning(s).")
        return 1
    print(f"PREFLIGHT PASSED with {len(r.warnings)} warning(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
