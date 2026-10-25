#!/usr/bin/env bash
# Writes throw-away env files for testing the deploy kit (CI and local checks), never for a server:
#   scripts/deploy/make-test-env.sh good <file>   every required value filled with random secrets
#   scripts/deploy/make-test-env.sh bad  <file>   the example file as shipped (placeholders, short keys)
set -euo pipefail

kind=${1:?usage: make-test-env.sh good|bad <file>}
out=${2:?usage: make-test-env.sh good|bad <file>}
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
example="$repo/.env.production.example"
domain=alakh-ci.in

rand() { openssl rand -hex "$1"; }

case "$kind" in
  good)
    jwt=$(rand 32)
    internal=$(rand 32)
    metrics=$(rand 32)
    pg=$(rand 24)
    sed \
      -e "s/REPLACE_ME@REPLACE_ME\.in/ops@$domain/" \
      -e "s/REPLACE_ME\.in/$domain/g" \
      -e "s/^JWT_SECRET_KEY=.*/JWT_SECRET_KEY=$jwt/" \
      -e "s/^INTERNAL_API_KEY=.*/INTERNAL_API_KEY=$internal/" \
      -e "s/^METRICS_TOKEN=.*/METRICS_TOKEN=$metrics/" \
      -e "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$pg/" \
      "$example" > "$out"
    ;;
  bad)
    cp "$example" "$out"
    {
      echo "CORS_ORIGINS=*"
      echo "RAZORPAY_KEY_ID=rzp_test_abc"
    } >> "$out"
    ;;
  *)
    echo "unknown kind: $kind (use good or bad)" >&2
    exit 2
    ;;
esac
chmod 600 "$out"
echo "wrote $out"
