#!/bin/sh
# Proves a backup can be restored: checks the checksums, restores every dump into a scratch
# database, checks it has its tables and migration version, then drops the scratch copy.
# Nothing existing is touched. Exits non-zero if any database fails.
#
#   verify.sh [backup dir]     default: the latest backup in BACKUP_DIR (/backups)
set -eu

BACKUP_DIR=${BACKUP_DIR:-/backups}
dir=${1:-$BACKUP_DIR/$(cat "$BACKUP_DIR/LATEST")}
log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) verify: $*"; }

[ -f "$dir/SHA256SUMS" ] || { log "$dir is not a complete backup"; exit 1; }
(cd "$dir" && sha256sum -c SHA256SUMS >/dev/null 2>&1) || { log "checksum mismatch in $dir"; exit 1; }

failed=0
for dump in "$dir"/*.dump; do
  db=$(basename "$dump" .dump)
  scratch="verify_${db}_$$"
  expected=$(sed -n "s/^database=$db .*tables=\([0-9]*\)$/\1/p" "$dir/MANIFEST")
  psql -d postgres -qc "create database \"$scratch\""
  if pg_restore --no-owner --exit-on-error --dbname="$scratch" "$dump" 2>"/tmp/$scratch.err"; then
    tables=$(psql -d "$scratch" -Atc "select count(*) from information_schema.tables where table_schema='public'")
    version=$(psql -d "$scratch" -Atc "select version_num from alembic_version" 2>/dev/null || echo "none")
    if [ "$tables" = "${expected:-$tables}" ]; then
      log "ok      $db: $tables tables, migration $version"
    else
      log "FAILED  $db: $tables tables restored, $expected expected"
      failed=1
    fi
  else
    log "FAILED  $db: $(tail -1 "/tmp/$scratch.err")"
    failed=1
  fi
  psql -d postgres -qc "drop database if exists \"$scratch\""
  rm -f "/tmp/$scratch.err"
done

if [ "$failed" = 0 ]; then
  date -u +%Y-%m-%dT%H:%M:%SZ > "$dir/VERIFIED"
  log "backup $dir restores cleanly"
fi
exit "$failed"
