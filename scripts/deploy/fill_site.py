#!/usr/bin/env python3
"""Fills the public site's [PLACEHOLDERS] and app-link files from deploy/site-details.env.

    python3 scripts/deploy/fill_site.py [--details FILE] [--site DIR] [--check]

Every highlighted `<span class="placeholder">[...]</span>` in deploy/site/*.html whose value is set is
replaced by the plain value; the REPLACE_WITH_... markers in .well-known/ get the Android signing
fingerprint and Apple Team ID. Values that are empty stay as placeholders and are listed at the end,
so the script can be run again as details arrive. --check changes nothing and exits 1 while
anything is unfilled. Standard library only.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# Placeholder text on the pages -> key in site-details.env.
PLACEHOLDERS = {
    "COMPANY LEGAL NAME": "COMPANY_LEGAL_NAME",
    "REGISTERED ADDRESS": "REGISTERED_ADDRESS",
    "CIN": "CIN",
    "CITY": "JURISDICTION_CITY",
    "GRIEVANCE OFFICER NAME": "GRIEVANCE_OFFICER_NAME",
    "DESIGNATION": "GRIEVANCE_OFFICER_DESIGNATION",
    "GRIEVANCE EMAIL": "GRIEVANCE_EMAIL",
    "GRIEVANCE PHONE": "GRIEVANCE_PHONE",
    "HOURS": "GRIEVANCE_HOURS",
    "HOURS, e.g. Mon–Sat, 10:00–18:00 IST": "GRIEVANCE_HOURS",
    "NODAL CONTACT NAME, EMAIL": "NODAL_CONTACT",
    "SUPPORT EMAIL": "SUPPORT_EMAIL",
    "EFFECTIVE DATE": "EFFECTIVE_DATE",
    "HOSTING PROVIDER, REGION": "HOSTING_PROVIDER",
    "MSG91 / TWILIO": "SMS_PROVIDER_NAME",
    "EMAIL PROVIDER": "EMAIL_PROVIDER_NAME",
    "180 days": "CHAT_RETENTION",
    "1 year": "SECURITY_LOG_RETENTION",
    "14 days": "BACKUP_RETENTION",
    "No refund / 50% refund": "LATE_CANCEL_REFUND",
    "48 hours": "DISPUTE_WINDOW",
    "7 days": "DISPUTE_DECISION_TIME",
    "15": "NO_SHOW_GRACE_MINUTES",
}

SPAN = re.compile(r'<span class="placeholder">\[([^\]<]+)\]</span>')
FINGERPRINT = re.compile(r"^[0-9A-F]{2}(:[0-9A-F]{2}){31}$")
TEAM_ID = re.compile(r"^[A-Z0-9]{10}$")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ANDROID_MARKER = "REPLACE_WITH_PLAY_APP_SIGNING_SHA256_FINGERPRINT"
APPLE_MARKER = "REPLACE_WITH_APPLE_TEAM_ID"


def read_details(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise SystemExit(f"{path}:{number}: expected KEY=value, got {raw!r}")
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def validate(values: dict[str, str]) -> list[str]:
    problems = []
    for key in ("GRIEVANCE_EMAIL", "SUPPORT_EMAIL"):
        if values.get(key) and not EMAIL.match(values[key]):
            problems.append(f"{key} is not an email address: {values[key]!r}")
    for fingerprint in fingerprints(values):
        if not FINGERPRINT.match(fingerprint):
            problems.append(
                f"ANDROID_SHA256_FINGERPRINT {fingerprint!r} is not a SHA-256 fingerprint (32 pairs like AB:CD:...)"
            )
    team = values.get("APPLE_TEAM_ID", "")
    if team and not TEAM_ID.match(team):
        problems.append(f"APPLE_TEAM_ID {team!r} is not a 10-character Team ID")
    if values.get("NO_SHOW_GRACE_MINUTES") and not values["NO_SHOW_GRACE_MINUTES"].isdigit():
        problems.append("NO_SHOW_GRACE_MINUTES must be a whole number of minutes")
    return problems


def fingerprints(values: dict[str, str]) -> list[str]:
    raw = values.get("ANDROID_SHA256_FINGERPRINT", "")
    return [f.strip().upper() for f in raw.split(",") if f.strip()]


def fill_page(text: str, values: dict[str, str]) -> tuple[str, set[str]]:
    """The page with every known, set placeholder replaced; and the placeholders left."""
    left: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        label = match.group(1)
        key = PLACEHOLDERS.get(label)
        value = values.get(key, "") if key else ""
        if not value:
            left.add(f"[{label}]" + (f" ({key})" if key else " (not known to fill_site.py)"))
            return match.group(0)
        return html.escape(value, quote=False)

    return SPAN.sub(replace, text), left


def fill_assetlinks(text: str, values: dict[str, str]) -> tuple[str, set[str]]:
    if ANDROID_MARKER not in text:
        return text, set()
    prints = fingerprints(values)
    if not prints:
        return text, {"Android signing fingerprint (ANDROID_SHA256_FINGERPRINT)"}
    data = json.loads(text)
    for statement in data:
        target = statement.get("target", {})
        if ANDROID_MARKER in target.get("sha256_cert_fingerprints", []):
            target["sha256_cert_fingerprints"] = prints
    return json.dumps(data, indent=2) + "\n", set()


def fill_aasa(text: str, values: dict[str, str]) -> tuple[str, set[str]]:
    if APPLE_MARKER not in text:
        return text, set()
    team = values.get("APPLE_TEAM_ID", "")
    if not team:
        return text, {"Apple Team ID (APPLE_TEAM_ID; only needed once the iOS app exists)"}
    return text.replace(APPLE_MARKER, team), set()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--details", type=Path, default=REPO / "deploy" / "site-details.env")
    parser.add_argument("--site", type=Path, default=REPO / "deploy" / "site")
    parser.add_argument("--check", action="store_true", help="change nothing; exit 1 while anything is unfilled")
    args = parser.parse_args(argv)

    if not args.details.is_file():
        print(
            f"{args.details} not found. Start from the example:\n"
            f"  cp deploy/site-details.example.env deploy/site-details.env",
            file=sys.stderr,
        )
        return 2
    values = read_details(args.details)
    problems = validate(values)
    if problems:
        for problem in problems:
            print(f"error: {problem}", file=sys.stderr)
        return 2

    jobs = [(page, fill_page) for page in sorted(args.site.glob("*.html"))]
    jobs += [
        (args.site / ".well-known" / "assetlinks.json", fill_assetlinks),
        (args.site / ".well-known" / "apple-app-site-association", fill_aasa),
    ]
    remaining: dict[str, set[str]] = {}
    changed = []
    for path, fill in jobs:
        if not path.is_file():
            continue
        before = path.read_text(encoding="utf-8")
        after, left = fill(before, values)
        if left:
            remaining[path.relative_to(args.site).as_posix()] = left
        if after != before:
            changed.append(path.relative_to(args.site).as_posix())
            if not args.check:
                path.write_text(after, encoding="utf-8", newline="\n")

    verb = "would fill" if args.check else "filled"
    for name in changed:
        print(f"{verb}  {name}")
    if remaining:
        print("\nStill to fill in (set these in the details file and run again):")
        for name, left in sorted(remaining.items()):
            print(f"  {name}: {', '.join(sorted(left))}")
    else:
        print("\nEvery placeholder is filled. Review the pages, have a lawyer read them, then commit deploy/site.")
    if args.check and (changed or remaining):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
