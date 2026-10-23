#!/usr/bin/env bash
# =============================================================================
# AlakhService — deploy, update and roll back on a single server (docs/DEPLOYMENT.md)
#
#   scripts/deploy/deploy.sh deploy     first install or update: pull, check, build, restart, test
#   scripts/deploy/deploy.sh rollback   go back to the images of the previous deploy
#   scripts/deploy/deploy.sh status     containers, versions, last backup, disk
#   scripts/deploy/deploy.sh logs [service]
#   scripts/deploy/deploy.sh backup     back up every database now (verified), then copy off-site
#   scripts/deploy/deploy.sh smoke      test the live sites through Caddy
#   scripts/deploy/deploy.sh restart    start/restart the deployed version (no build), e.g. after a restore
#
# Options (deploy):   --no-pull      deploy the code as it is checked out (no git pull)
#                     --skip-backup  do not back up the databases before migrating
#                     --allow-dirty  deploy even with uncommitted changes
# Options (rollback): --yes          do not ask before undoing database migrations
#
# Environment: ENV_FILE (default .env.production).
#
# Safe to re-run: a deploy of the commit that is already live only restarts what changed.
# Every image is tagged with the git commit; deploy/.state/ remembers the current and previous
# tags so `rollback` can switch back without rebuilding.
# =============================================================================
set -Eeuo pipefail

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$REPO"

ENV_FILE=${ENV_FILE:-.env.production}
STATE_DIR="$REPO/deploy/.state"
IMAGE_PREFIX=localhost/alakhservice

# Every service built from this repository (each has its own image and, except the gateway and
# Caddy, its own database and Alembic migrations).
PYTHON_SERVICES=(
  auth_service user_service shop_service booking_service payment_service notification_service
  tracking_service queue_service analytics_service dispute_service
  trust_risk_service admin_service compliance_service pricing_engine service_catalog_service
)
BUILT_SERVICES=("${PYTHON_SERVICES[@]}" api_gateway caddy)
MONITORING_SERVICES=(prometheus alertmanager grafana blackbox node_exporter backup_metrics)

if [ -t 1 ]; then
  BOLD=$'\033[1m' GREEN=$'\033[32m' YELLOW=$'\033[33m' RED=$'\033[31m' RESET=$'\033[0m'
else
  BOLD="" GREEN="" YELLOW="" RED="" RESET=""
fi
step() { printf '\n%s==> %s%s\n' "$BOLD" "$*" "$RESET"; }
ok() { printf '  %sok%s   %s\n' "$GREEN" "$RESET" "$*"; }
warn() { printf '  %sWARN%s %s\n' "$YELLOW" "$RESET" "$*" >&2; }
die() {
  printf '\n%sERROR:%s %s\n' "$RED" "$RESET" "$*" >&2
  exit 1
}

# Value of KEY in the env file (last one wins, surrounding quotes removed).
env_value() {
  local line
  line=$(grep -E "^[[:space:]]*$1=" "$ENV_FILE" | tail -n 1 || true)
  line=${line#*=}
  line=${line%\"}
  line=${line#\"}
  line=${line%\'}
  line=${line#\'}
  printf '%s' "$line"
}

compose() {
  docker compose --env-file "$ENV_FILE" -f docker-compose.yml -f docker-compose.prod.yml "$@"
}

require_env_file() {
  [ -f "$ENV_FILE" ] || die "$ENV_FILE not found. Create it: cp .env.production.example $ENV_FILE (docs/DEPLOYMENT.md, step 5)"
  # Compose reads COMPOSE_PROFILES from the environment; take it from the env file.
  COMPOSE_PROFILES=$(env_value COMPOSE_PROFILES)
  export COMPOSE_PROFILES
}

backup_dir() {
  local dir
  dir=$(env_value BACKUP_HOST_DIR)
  printf '%s' "${dir:-./backups}"
}

monitoring_enabled() { [[ ",$COMPOSE_PROFILES," == *",monitoring,"* ]]; }

read_state() { cat "$STATE_DIR/$1" 2>/dev/null || true; }
write_state() {
  mkdir -p "$STATE_DIR"
  printf '%s\n' "$2" > "$STATE_DIR/$1"
}

images_exist() {
  local tag=$1 svc
  for svc in "${BUILT_SERVICES[@]}"; do
    docker image inspect "$IMAGE_PREFIX/$svc:$tag" > /dev/null 2>&1 || return 1
  done
}

show_failure() {
  local svc=$1
  printf '\n%sLast log lines of %s:%s\n' "$BOLD" "$svc" "$RESET" >&2
  compose logs --no-color --tail=60 "$svc" >&2 || true
}

# Starts (or recreates, if its image or settings changed) one service and waits for /ready.
roll() {
  local svc=$1
  if compose up -d --no-deps --wait --wait-timeout 300 "$svc" > /dev/null 2>&1; then
    ok "$svc"
  else
    show_failure "$svc"
    die "$svc did not become healthy. The services before it are on the new version, the rest are untouched.
Fix the problem shown above and run the deploy again, or go back with: make prod-rollback"
  fi
}

roll_all() {
  local svc
  step "Restarting services one at a time (each waits until /ready answers)"
  for svc in "${PYTHON_SERVICES[@]}"; do roll "$svc"; done
  roll api_gateway
  # The backup service turns healthy only after its first backup, so do not wait for it.
  compose up -d --no-deps backup > /dev/null
  ok "backup (scheduled every $(env_value BACKUP_INTERVAL_HOURS) h)"
  roll caddy
  if monitoring_enabled; then
    compose up -d --no-deps "${MONITORING_SERVICES[@]}" > /dev/null
    ok "monitoring (${MONITORING_SERVICES[*]})"
  fi
  # Anything else in the files (and remove containers of services that no longer exist).
  compose up -d --remove-orphans > /dev/null
}

prune_images() {
  local keep_current keep_previous ref
  keep_current=$(read_state current_tag)
  keep_previous=$(read_state previous_tag)
  while read -r ref; do
    case "$ref" in
      *":$keep_current" | *":$keep_previous") ;;
      *) docker image rm "$ref" > /dev/null 2>&1 || true ;;
    esac
  done < <(docker images --format '{{.Repository}}:{{.Tag}}' --filter "reference=$IMAGE_PREFIX/*")
  docker image prune -f > /dev/null 2>&1 || true
}

# ---------------------------------------------------------------------------
# smoke: through Caddy, the way a visitor reaches the sites
# ---------------------------------------------------------------------------

cmd_smoke() {
  require_env_file
  local domain failures=0 code body i
  local insecure=()
  domain=$(env_value DOMAIN)
  [ -n "$domain" ] || die "DOMAIN is empty in $ENV_FILE"
  local resolve=(--resolve "api.$domain:443:127.0.0.1" --resolve "shop.$domain:443:127.0.0.1"
    --resolve "admin.$domain:443:127.0.0.1")

  step "Smoke test through Caddy (https://api.$domain, shop., admin.)"
  # A first deploy may still be fetching certificates; wait for up to 2 minutes.
  for i in $(seq 1 24); do
    if curl -fsS --max-time 10 "${resolve[@]}" "https://api.$domain/health" > /dev/null 2>&1; then break; fi
    if [ "$i" = 24 ]; then
      if curl -fsSk --max-time 10 "${resolve[@]}" "https://api.$domain/health" > /dev/null 2>&1; then
        warn "the HTTPS certificate is not valid yet: check that DNS points at this server and run: make prod-logs S=caddy"
        insecure=(-k)
      else
        warn "https://api.$domain/health does not answer through Caddy"
        failures=$((failures + 1))
      fi
    else
      sleep 5
    fi
  done

  # expect <description> <url> <accepted status codes regex> [text the body must contain]
  expect() {
    local description=$1 url=$2 codes=$3 needle=${4:-}
    body=$(curl -sS "${insecure[@]}" --max-time 15 "${resolve[@]}" -o - -w '\n%{http_code}' "$url" 2>/dev/null || printf '\n000')
    code=${body##*$'\n'}
    if [[ "$code" =~ ^($codes)$ ]] && { [ -z "$needle" ] || [[ "$body" == *"$needle"* ]]; }; then
      ok "$description ($code)"
    else
      warn "$description: got HTTP $code from $url"
      failures=$((failures + 1))
    fi
  }
  expect "gateway is up" "https://api.$domain/health" 200 healthy
  expect "API reaches the services" "https://api.$domain/api/v1/services" '2[0-9][0-9]'
  expect "/metrics is hidden from the internet" "https://api.$domain/metrics" 404
  expect "shop dashboard" "https://shop.$domain/" 200 'id="root"'
  expect "shop dashboard client routes" "https://shop.$domain/login" 200 'id="root"'
  # 403 is right when ADMIN_ALLOWED_IPS does not include this server.
  expect "admin dashboard" "https://admin.$domain/" '200|403'

  if [ "$failures" -gt 0 ]; then
    die "$failures smoke check(s) failed. See: make prod-status, make prod-logs S=<service>"
  fi
}

# ---------------------------------------------------------------------------
# deploy
# ---------------------------------------------------------------------------

cmd_deploy() {
  local pull=1 backup=1 allow_dirty=0 arg
  for arg in "$@"; do
    case "$arg" in
      --no-pull) pull=0 ;;
      --skip-backup) backup=0 ;;
      --allow-dirty) allow_dirty=1 ;;
      *) die "unknown option for deploy: $arg" ;;
    esac
  done
  require_env_file

  step "Code"
  if git rev-parse --git-dir > /dev/null 2>&1; then
    if [ -n "$(git status --porcelain --untracked-files=no)" ] && [ "$allow_dirty" = 0 ]; then
      git status --short --untracked-files=no >&2
      die "this checkout has uncommitted changes (above). Commit or discard them, or pass --allow-dirty."
    fi
    if [ "$pull" = 1 ]; then
      git pull --ff-only || die "git pull failed (local commits or a diverged branch?). Fix it, or deploy with --no-pull."
    fi
    ok "at commit $(git log -1 --format='%h %s')"
  else
    warn "not a git checkout: images are tagged by date and cannot be matched to a commit"
  fi

  step "Preflight"
  python3 scripts/deploy/preflight.py --env-file "$ENV_FILE" || die "preflight failed; fix the FAIL lines above and run again."

  local tag current previous first_time=0
  tag=$(git rev-parse --short=12 HEAD 2>/dev/null || date -u +%Y%m%d%H%M%S)
  if [ -n "$(git status --porcelain --untracked-files=no 2>/dev/null)" ]; then tag="$tag-dirty"; fi
  current=$(read_state current_tag)
  previous=$(read_state previous_tag)
  docker volume inspect alakhservice_postgres_data > /dev/null 2>&1 || first_time=1
  export IMAGE_TAG=$tag

  step "Building images for $tag (the first build takes 5-15 minutes)"
  compose pull --ignore-buildable --quiet
  compose build --pull
  ok "images built: $IMAGE_PREFIX/<service>:$tag"

  step "Database and Redis"
  compose up -d --no-deps --wait postgres redis > /dev/null
  ok "postgres and redis are healthy"

  if [ "$first_time" = 0 ] && [ "$backup" = 1 ]; then
    step "Backing up every database before migrating"
    compose run --rm --no-deps --entrypoint /scripts/backup.sh backup ||
      die "the pre-deploy backup failed; nothing was changed. Fix it, or deploy with --skip-backup."
    ok "backup written: $(backup_dir)/$(cat "$(backup_dir)/LATEST" 2> /dev/null || echo '?')"
  fi

  # Remember what to roll back to before anything is restarted.
  if [ "$tag" != "$current" ]; then
    [ -n "$current" ] && write_state previous_tag "$current"
    write_state current_tag "$tag"
    previous=${current:-$previous}
  fi

  # Each service applies its own migrations (alembic upgrade head) before it starts serving.
  roll_all

  cmd_smoke

  prune_images
  local domain
  domain=$(env_value DOMAIN)
  step "Deployed $tag"
  printf '  API              https://api.%s/api/v1\n' "$domain"
  printf '  Shop dashboard   https://shop.%s\n' "$domain"
  printf '  Admin dashboard  https://admin.%s\n' "$domain"
  if monitoring_enabled; then
    printf '  Grafana          ssh -L 3001:127.0.0.1:3001 <you>@<this server>, then http://localhost:3001\n'
  fi
  [ -n "$previous" ] && printf '  Roll back with   make prod-rollback   (to %s)\n' "$previous"
  if [ "$first_time" = 1 ]; then
    printf '\n  First deploy: register your account in the shop dashboard or app, then make it an admin:\n'
    printf '    make prod-make-admin ACCOUNT=you@example.com\n'
  fi
}

# ---------------------------------------------------------------------------
# rollback
# ---------------------------------------------------------------------------

alembic_heads() {
  docker run --rm --network none --entrypoint alembic "$IMAGE_PREFIX/$1:$2" heads 2> /dev/null |
    awk '{print $1}' | sort | tr '\n' ' ' | sed 's/ $//'
}

cmd_rollback() {
  local yes=0 arg
  for arg in "$@"; do
    case "$arg" in
      --yes | -y) yes=1 ;;
      *) die "unknown option for rollback: $arg" ;;
    esac
  done
  require_env_file

  local current previous svc
  current=$(read_state current_tag)
  previous=$(read_state previous_tag)
  [ -n "$previous" ] || die "no previous deploy is recorded in deploy/.state; nothing to roll back to."
  images_exist "$previous" || die "the images for $previous are gone (pruned?). Check out that commit and deploy it instead:
  git checkout $previous && scripts/deploy/deploy.sh deploy --no-pull"
  step "Rolling back from $current to $previous"

  # A newer version may have migrated a database past what the older code knows; the older
  # code would then refuse to start. Undo those migrations with the newer image, which has them.
  local to_downgrade=() cur_heads prev_heads
  declare -A target=()
  for svc in "${PYTHON_SERVICES[@]}"; do
    cur_heads=$(alembic_heads "$svc" "$current")
    prev_heads=$(alembic_heads "$svc" "$previous")
    if [ -n "$prev_heads" ] && [ "$cur_heads" != "$prev_heads" ]; then
      [[ "$prev_heads" == *" "* ]] && die "$svc has several migration heads ($prev_heads); roll back by restoring the pre-deploy backup instead (docs/DISASTER_RECOVERY.md)."
      to_downgrade+=("$svc")
      target[$svc]=$prev_heads
    fi
  done

  if [ "${#to_downgrade[@]}" -gt 0 ]; then
    printf '\n  The newer version changed the database of: %s\n' "${to_downgrade[*]}"
    printf '  Rolling back undoes those migrations; data stored only in new tables or columns is lost.\n'
    printf '  A backup was taken before the deploy (see backups/LATEST and docs/DISASTER_RECOVERY.md).\n'
    if [ "$yes" = 0 ]; then
      local answer=""
      read -r -p "  Continue? [y/N] " answer || true
      [[ "$answer" =~ ^[Yy]$ ]] || die "rollback cancelled; nothing was changed."
    fi
  fi

  export IMAGE_TAG=$previous
  for svc in "${PYTHON_SERVICES[@]}"; do
    if [ -n "${target[$svc]:-}" ]; then
      compose stop "$svc" > /dev/null
      IMAGE_TAG=$current compose run --rm --no-deps -T "$svc" alembic downgrade "${target[$svc]}" ||
        die "downgrading $svc's database failed; restore the pre-deploy backup (docs/DISASTER_RECOVERY.md)."
      ok "$svc database back at ${target[$svc]}"
    fi
  done

  roll_all
  # Swap, so running rollback again returns to the newer version.
  write_state current_tag "$previous"
  write_state previous_tag "$current"
  cmd_smoke
  step "Rolled back to $previous"
  printf '  The checkout is still at the newer code; the next "make prod-deploy" deploys it again.\n'
  printf '  To stay on %s for now, run: git checkout %s\n' "$previous" "${previous%-dirty}"
}

# ---------------------------------------------------------------------------
# status, logs, backup
# ---------------------------------------------------------------------------

cmd_status() {
  require_env_file
  step "Version"
  printf '  current: %s\n  previous: %s\n' "$(read_state current_tag)" "$(read_state previous_tag)"
  step "Containers"
  compose ps --format 'table {{.Service}}\t{{.Status}}\t{{.Image}}'
  step "Last verified backup"
  local dir last
  dir=$(backup_dir)
  if [ -f "$dir/.last_success" ]; then
    last=$(cat "$dir/.last_success")
    printf '  %s (%s hours ago), latest folder: %s\n' "$(date -u -d "@$last" '+%Y-%m-%d %H:%M UTC' 2> /dev/null || echo "$last")" \
      "$((($(date +%s) - last) / 3600))" "$(cat "$dir/LATEST" 2> /dev/null || echo '?')"
  else
    printf '  none yet (the first scheduled backup runs about %s hours after the backup service starts;\n' "$(env_value BACKUP_INTERVAL_HOURS)"
    printf '  run one now with: make prod-backup)\n'
  fi
  step "Disk"
  df -h "$REPO" | sed 's/^/  /'
  docker system df 2> /dev/null | sed 's/^/  /' || true
}

cmd_restart() {
  require_env_file
  local tag
  tag=$(read_state current_tag)
  [ -n "$tag" ] || die "nothing has been deployed yet; run: make prod-deploy"
  images_exist "$tag" || die "the images for $tag are missing; run: make prod-deploy"
  export IMAGE_TAG=$tag
  compose up -d --no-deps --wait postgres redis > /dev/null
  roll_all
  cmd_smoke
}

cmd_logs() {
  require_env_file
  compose logs -f --tail=200 "$@"
}

cmd_backup() {
  require_env_file
  step "Backing up every database"
  compose run --rm --no-deps --entrypoint /scripts/backup.sh backup
  step "Verifying the backup restores"
  compose run --rm --no-deps --entrypoint /scripts/verify.sh backup
  if [ -n "$(env_value OFFSITE_RCLONE_REMOTE)" ]; then
    step "Copying off-site"
    ENV_FILE="$ENV_FILE" scripts/deploy/offsite-backup.sh
  else
    warn "OFFSITE_RCLONE_REMOTE is empty: this backup exists only on this server"
  fi
}

usage() {
  awk 'NR > 2 && /^# ====/ { exit } NR > 2' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

command=${1:-}
[ $# -gt 0 ] && shift
case "$command" in
  deploy) cmd_deploy "$@" ;;
  rollback) cmd_rollback "$@" ;;
  status) cmd_status ;;
  logs) cmd_logs "$@" ;;
  backup) cmd_backup ;;
  smoke) cmd_smoke ;;
  restart) cmd_restart ;;
  -h | --help | help | "") usage ;;
  *)
    usage >&2
    exit 2
    ;;
esac
