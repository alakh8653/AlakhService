#!/bin/sh
# Backs up every service database, one file each, and prunes old backups.
#
#   BACKUP_DIR/<UTC timestamp>/<database>.dump   pg_dump custom format (compressed; pg_restore
#                                                can bring back one database or one table)
#                             /globals.sql        roles, so a fresh server can take the dumps
#                             /SHA256SUMS         checked before anything is restored
#                             /MANIFEST           when, which server, size and tables per database
#
# Connection: the usual PGHOST/PGPORT/PGUSER/PGPASSWORD. Settings (defaults):
#   BACKUP_DIR=/backups  BACKUP_KEEP_DAYS=14  BACKUP_MIN_KEEP=3
#   BACKUP_DATABASES     space-separated; default: every non-template database on the server
#   BACKUP_UPLOAD_COMMAND  run after a successful backup with the backup's path as $1, e.g.
#                          'aws s3 cp --recursive "$1" s3://my-bucket/alakh/$(basename "$1")'
#                          Keep a copy off this machine: a backup on the same disk as the
#                          database does not survive losing that disk.
set -eu

BACKUP_DIR=${BACKUP_DIR:-/backups}
KEEP_DAYS=${BACKUP_KEEP_DAYS:-14}
MIN_KEEP=${BACKUP_MIN_KEEP:-3}

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) backup: $*"; }

stamp=$(date -u +%Y%m%dT%H%M%SZ)
target="$BACKUP_DIR/$stamp"
partial="$BACKUP_DIR/.partial-$stamp"
mkdir -p "$partial"
# A failed run leaves no half-written backup that looks complete.
trap 'rm -rf "$partial"' EXIT

databases=${BACKUP_DATABASES:-$(psql -d postgres -Atc \
  "select datname from pg_database where not datistemplate and datname <> 'postgres' order by 1")}
[ -n "$databases" ] || { log "no databases found"; exit 1; }

pg_dumpall --globals-only --no-role-passwords > "$partial/globals.sql"
{
  echo "created_at=$stamp"
  echo "server=$(psql -d postgres -Atc 'show server_version')"
} > "$partial/MANIFEST"

for db in $databases; do
  log "dumping $db"
  pg_dump --format=custom --compress=6 --no-owner --dbname="$db" --file="$partial/$db.dump"
  tables=$(psql -d "$db" -Atc "select count(*) from information_schema.tables where table_schema='public'")
  echo "database=$db bytes=$(wc -c < "$partial/$db.dump" | tr -d ' ') tables=$tables" >> "$partial/MANIFEST"
done

(cd "$partial" && sha256sum ./*.dump globals.sql MANIFEST > SHA256SUMS)
mv "$partial" "$target"
trap - EXIT
log "wrote $target ($(du -sh "$target" | cut -f1))"

if [ -n "${BACKUP_UPLOAD_COMMAND:-}" ]; then
  log "uploading"
  sh -c "$BACKUP_UPLOAD_COMMAND" upload "$target"
fi

# Prune: older than KEEP_DAYS, but never below MIN_KEEP complete backups.
count=$(find "$BACKUP_DIR" -mindepth 1 -maxdepth 1 -type d -name '20*' | wc -l)
for old in $(find "$BACKUP_DIR" -mindepth 1 -maxdepth 1 -type d -name '20*' -mtime +"$KEEP_DAYS" | sort); do
  [ "$count" -gt "$MIN_KEEP" ] || break
  log "removing expired $old"
  rm -rf "$old"
  count=$((count - 1))
done
# Interrupted runs from before.
find "$BACKUP_DIR" -mindepth 1 -maxdepth 1 -type d -name '.partial-*' -mmin +1440 -exec rm -rf {} +

echo "$stamp" > "$BACKUP_DIR/LATEST"
