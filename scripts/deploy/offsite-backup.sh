#!/usr/bin/env bash
# Copies the verified database backups (backups/<timestamp>/) to off-site storage with rclone.
#
# A backup on the same disk as the database does not survive losing that disk or the server,
# so run this from cron on the server, an hour or so after the scheduled backup, e.g.:
#
#   sudo crontab -e
#   30 4 * * * cd /opt/alakhservice && scripts/deploy/offsite-backup.sh >> /var/log/alakh-offsite.log 2>&1
#
# Setup (once): install rclone (https://rclone.org/install/), run `rclone config` to add a
# remote (Amazon S3 in ap-south-1, Cloudflare R2, Backblaze B2, Google Drive, ...), ideally
# wrapped in an rclone "crypt" remote so the provider only sees encrypted files, then set
# OFFSITE_RCLONE_REMOTE=<remote>:<bucket or folder> in .env.production. Turn on versioning or
# object lock at the provider so a mistake (or an attacker) here cannot delete the copies.
#
# Only adds and updates files off-site (rclone copy); pruning old copies is left to the
# provider's lifecycle rules, so a wiped server can never wipe the off-site copies.
set -euo pipefail

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$REPO"
ENV_FILE=${ENV_FILE:-.env.production}

env_value() {
  local line
  line=$(grep -E "^[[:space:]]*$1=" "$ENV_FILE" | tail -n 1 || true)
  line=${line#*=}
  line=${line%\"}
  line=${line#\"}
  printf '%s' "$line"
}

[ -f "$ENV_FILE" ] || {
  echo "$ENV_FILE not found" >&2
  exit 1
}
remote=$(env_value OFFSITE_RCLONE_REMOTE)
backup_dir=$(env_value BACKUP_HOST_DIR)
backup_dir=${backup_dir:-./backups}

if [ -z "$remote" ]; then
  echo "OFFSITE_RCLONE_REMOTE is empty in $ENV_FILE; nothing to do" >&2
  exit 1
fi
command -v rclone > /dev/null || {
  echo "rclone is not installed: https://rclone.org/install/" >&2
  exit 1
}
[ -f "$backup_dir/LATEST" ] || {
  echo "no backup in $backup_dir yet" >&2
  exit 1
}

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) copying $backup_dir to $remote"
# Half-written backups live in .partial-* until complete; --min-age is a second guard.
rclone copy "$backup_dir" "$remote" --min-age 2m --exclude ".last_success" --exclude "LATEST" --exclude ".partial-*/**" --stats-one-line -v
rclone copyto "$backup_dir/LATEST" "$remote/LATEST"
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) off-site copy done (latest: $(cat "$backup_dir/LATEST"))"
