#!/bin/sh
# Runs in the compose "backup" service: a backup every BACKUP_INTERVAL_HOURS (default 24), each one
# restored into scratch databases straight away to prove it works. The service's healthcheck fails
# when the last good, verified backup is older than two intervals, so a silent failure shows up.
set -u
interval_hours=${BACKUP_INTERVAL_HOURS:-24}
until pg_isready -q; do sleep 2; done
while true; do
  if /scripts/backup.sh && /scripts/verify.sh; then
    date -u +%s > "${BACKUP_DIR:-/backups}/.last_success"
  else
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) schedule: backup FAILED; will retry next interval" >&2
  fi
  sleep $((interval_hours * 3600))
done
