#!/bin/sh
# Restores databases from a backup made by backup.sh.
#
#   restore.sh <backup dir> [database ...]            restore next to the originals, as
#                                                      <database>_restored, for inspection or a
#                                                      manual switch-over (nothing is overwritten)
#   restore.sh --in-place --yes <backup dir> [db ...]  replace the live databases (stop the
#                                                      services first; this is destructive)
#
# Without database names, every database in the backup is restored. Checksums are verified first.
# A full in-place restore (no database names) also puts back the uploaded files when
# RESTORE_FILES_ROOT is set: each files-<name>.tar.gz replaces the contents of $RESTORE_FILES_ROOT/<name>
# (the Makefile's restore-in-place targets mount the upload volumes there).
set -eu

in_place=0
confirmed=0
while [ $# -gt 0 ]; do
  case "$1" in
    --in-place) in_place=1 ;;
    --yes) confirmed=1 ;;
    -*) echo "unknown option $1" >&2; exit 2 ;;
    *) break ;;
  esac
  shift
done
[ $# -ge 1 ] || { sed -n '2,15p' "$0"; exit 2; }
dir=$1
shift
log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) restore: $*"; }

[ -f "$dir/SHA256SUMS" ] || { log "$dir is not a complete backup"; exit 1; }
(cd "$dir" && sha256sum -c SHA256SUMS >/dev/null 2>&1) || { log "checksum mismatch in $dir: refusing to restore"; exit 1; }
if [ "$in_place" = 1 ] && [ "$confirmed" != 1 ]; then
  log "--in-place replaces live data; add --yes once the services are stopped"
  exit 2
fi

full=0
[ $# -eq 0 ] && full=1
databases=${*:-$(for f in "$dir"/*.dump; do basename "$f" .dump; done)}
for db in $databases; do
  dump="$dir/$db.dump"
  [ -f "$dump" ] || { log "no dump for $db in $dir"; exit 1; }
  if [ "$in_place" = 1 ]; then
    target=$db
    psql -d postgres -qc "select pg_terminate_backend(pid) from pg_stat_activity where datname = '$db' and pid <> pg_backend_pid()" >/dev/null
    psql -d postgres -qc "drop database if exists \"$db\""
  else
    target="${db}_restored"
    psql -d postgres -qc "drop database if exists \"$target\""
  fi
  psql -d postgres -qc "create database \"$target\""
  pg_restore --no-owner --exit-on-error --dbname="$target" "$dump"
  log "restored $db into $target"
done

if [ "$in_place" = 1 ] && [ "$full" = 1 ] && [ -n "${RESTORE_FILES_ROOT:-}" ]; then
  for archive in "$dir"/files-*.tar.gz; do
    [ -f "$archive" ] || continue
    name=$(basename "$archive" .tar.gz)
    name=${name#files-}
    target="$RESTORE_FILES_ROOT/$name"
    [ -d "$target" ] || { log "no $target to restore $name into; skipped"; continue; }
    find "$target" -mindepth 1 -delete
    tar -xzf "$archive" -C "$target"
    log "restored files $name into $target"
  done
fi
