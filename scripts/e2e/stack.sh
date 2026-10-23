#!/usr/bin/env bash
# =============================================================================
# Runs the whole AlakhService backend on this machine, without Docker, for the end-to-end flow:
# every Python service under uvicorn (after its Alembic migrations) and the API gateway, against one
# PostgreSQL server (a database per service, as in docker-compose.yml) and one Redis.
#
#   scripts/e2e/stack.sh install            one virtualenv per service in $E2E_VENVS, gateway npm ci + build
#   scripts/e2e/stack.sh start              create databases, migrate, start everything (logs in $E2E_DIR/logs)
#   scripts/e2e/stack.sh make-admin EMAIL   grant admin to a registered account (used by flow.py)
#   scripts/e2e/stack.sh logs               print the tail of every log (CI, after a failure)
#   scripts/e2e/stack.sh stop
#
# Settings (environment): PGHOST PGPORT PGUSER PGPASSWORD (default localhost 5432 postgres postgres),
# REDIS_HOST/REDIS_PORT (localhost 6379), E2E_DIR (.e2e), E2E_VENVS ($E2E_DIR/venv), PYTHON (python3).
# The service ports match docker-compose.yml, so scripts/e2e/flow.py works against either.
# =============================================================================
set -Eeuo pipefail

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
E2E_DIR=${E2E_DIR:-$REPO/.e2e}
E2E_VENVS=${E2E_VENVS:-$E2E_DIR/venv}
PYTHON=${PYTHON:-python3}
export PGHOST=${PGHOST:-localhost} PGPORT=${PGPORT:-5432} PGUSER=${PGUSER:-postgres} PGPASSWORD=${PGPASSWORD:-postgres}
REDIS_HOST=${REDIS_HOST:-localhost}
REDIS_PORT=${REDIS_PORT:-6379}

# name port database redis-db (as in docker-compose.yml)
SERVICES=(
  "auth_service 8001 auth_db 0"
  "user_service 8002 user_db 1"
  "shop_service 8003 shop_db 2"
  "booking_service 8004 booking_db 3"
  "payment_service 8005 payment_db 4"
  "notification_service 8006 notification_db 5"
  "tracking_service 8007 tracking_db 6"
  "queue_service 8008 queue_db 7"
  "analytics_service 8010 analytics_db 9"
  "dispute_service 8011 dispute_db 10"
  "trust_risk_service 8012 trust_risk_db 11"
  "admin_service 8013 admin_db 12"
  "compliance_service 8014 compliance_db 13"
  "pricing_engine 8015 pricing_db 14"
  "service_catalog_service 8016 service_catalog_db 15"
)

SECRET=e2e-jwt-secret-0123456789abcdef0123456789
INTERNAL=e2e-internal-key-0123456789abcdef012345

common_env() {
  # Same names the compose file sets; every service gets all of them (unused ones are ignored).
  cat <<EOF
SECRET_KEY=$SECRET
JWT_SECRET_KEY=$SECRET
INTERNAL_API_KEY=$INTERNAL
ENVIRONMENT=development
AUTH_SERVICE_URL=http://127.0.0.1:8001
USER_SERVICE_URL=http://127.0.0.1:8002
SHOP_SERVICE_URL=http://127.0.0.1:8003
BOOKING_SERVICE_URL=http://127.0.0.1:8004
PAYMENT_SERVICE_URL=http://127.0.0.1:8005
NOTIFICATION_SERVICE_URL=http://127.0.0.1:8006
TRACKING_SERVICE_URL=http://127.0.0.1:8007
QUEUE_SERVICE_URL=http://127.0.0.1:8008
ANALYTICS_SERVICE_URL=http://127.0.0.1:8010
DISPUTE_SERVICE_URL=http://127.0.0.1:8011
TRUST_RISK_SERVICE_URL=http://127.0.0.1:8012
ADMIN_SERVICE_URL=http://127.0.0.1:8013
COMPLIANCE_SERVICE_URL=http://127.0.0.1:8014
PRICING_ENGINE_URL=http://127.0.0.1:8015
SERVICE_CATALOG_URL=http://127.0.0.1:8016
LEGAL_BASE_URL=http://localhost:8080
SMS_PROVIDER=none
EOF
}

service_env() { # name port db redis
  common_env
  echo "DATABASE_URL=postgresql+asyncpg://$PGUSER:$PGPASSWORD@$PGHOST:$PGPORT/$3"
  echo "REDIS_URL=redis://$REDIS_HOST:$REDIS_PORT/$4"
}

with_env() { # name port db redis -- command...
  local name=$1 port=$2 db=$3 redis=$4
  shift 5
  # shellcheck disable=SC2046
  env $(service_env "$name" "$port" "$db" "$redis" | xargs) "$@"
}

cmd_install() {
  mkdir -p "$E2E_VENVS"
  local pids=() entry name
  for entry in "${SERVICES[@]}"; do
    read -r name _ <<< "$entry"
    (
      [ -x "$E2E_VENVS/$name/bin/python" ] || "$PYTHON" -m venv "$E2E_VENVS/$name"
      "$E2E_VENVS/$name/bin/pip" install -q --disable-pip-version-check -r "$REPO/services/$name/requirements.txt"
    ) > "$E2E_DIR/install-$name.log" 2>&1 &
    pids+=($!)
  done
  local failed=0 pid
  for pid in "${pids[@]}"; do wait "$pid" || failed=1; done
  if [ "$failed" = 1 ]; then
    tail -n 30 "$E2E_DIR"/install-*.log
    echo "install failed" >&2
    exit 1
  fi
  (cd "$REPO/services/api_gateway" && npm ci --no-audit --no-fund --silent && npm run -s build)
  echo "installed"
}

cmd_start() {
  mkdir -p "$E2E_DIR/logs" "$E2E_DIR/pids"
  local entry name port db redis
  for entry in "${SERVICES[@]}"; do
    read -r name port db redis <<< "$entry"
    psql -d postgres -qtAc "select 1 from pg_database where datname = '$db'" | grep -q 1 ||
      psql -d postgres -qc "create database $db"
    (
      cd "$REPO/services/$name"
      with_env "$name" "$port" "$db" "$redis" -- "$E2E_VENVS/$name/bin/alembic" upgrade head
    ) > "$E2E_DIR/logs/$name.log" 2>&1 || { tail -n 40 "$E2E_DIR/logs/$name.log"; echo "$name: migrations failed" >&2; exit 1; }
    (
      cd "$REPO/services/$name"
      exec env $(service_env "$name" "$port" "$db" "$redis" | xargs) \
        "$E2E_VENVS/$name/bin/uvicorn" app.main:app --host 127.0.0.1 --port "$port"
    ) >> "$E2E_DIR/logs/$name.log" 2>&1 &
    echo $! > "$E2E_DIR/pids/$name"
  done
  (
    cd "$REPO/services/api_gateway"
    exec env $(common_env | xargs) PORT=3000 CORS_ORIGINS=http://localhost:5173 \
      REDIS_URL="redis://$REDIS_HOST:$REDIS_PORT/0" node dist/server.js
  ) > "$E2E_DIR/logs/api_gateway.log" 2>&1 &
  echo $! > "$E2E_DIR/pids/api_gateway"
  echo "started; logs in $E2E_DIR/logs"
}

cmd_make_admin() {
  local email=${1:?usage: stack.sh make-admin EMAIL}
  cd "$REPO/services/auth_service"
  with_env auth_service 8001 auth_db 0 -- "$E2E_VENVS/auth_service/bin/python" -m app.cli make-admin "$email"
}

cmd_logs() {
  local f
  for f in "$E2E_DIR"/logs/*.log; do
    echo "===== $(basename "$f") ====="
    tail -n 60 "$f"
  done
}

cmd_stop() {
  local f
  for f in "$E2E_DIR"/pids/*; do
    [ -f "$f" ] || continue
    kill "$(cat "$f")" 2>/dev/null || true
    rm -f "$f"
  done
  echo "stopped"
}

case "${1:-}" in
  install) cmd_install ;;
  start) cmd_start ;;
  make-admin) shift; cmd_make_admin "$@" ;;
  logs) cmd_logs ;;
  stop) cmd_stop ;;
  *)
    echo "usage: $0 install|start|make-admin EMAIL|logs|stop" >&2
    exit 2
    ;;
esac
