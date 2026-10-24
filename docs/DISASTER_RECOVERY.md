# Backups and disaster recovery

Every service keeps its data in its own PostgreSQL database (`auth_db`, `booking_db`,
`payment_db`, …). This page covers how those databases are backed up, how a backup is proven to
work, and how to bring data back.

## What runs

The `backup` service in `docker-compose.yml` runs `scripts/backup/schedule.sh`:

1. Every `BACKUP_INTERVAL_HOURS` (default 24) it runs **`backup.sh`**. Each database is dumped
   separately in PostgreSQL's custom format, which is compressed and lets you restore one database
   or one table. Roles, a manifest and SHA-256 checksums are written alongside. Each backup goes to
   `backups/<UTC timestamp>/`, and `backups/LATEST` names the newest.
2. It then runs **`verify.sh`** on that backup:
   - The checksums are checked.
   - Every dump is restored into a scratch database (`verify_<db>_<pid>`), and the number of
     tables and the migration version are checked against the manifest.
   - The scratch copy is then dropped.

   A backup that has never been restored is a hope, not a backup.
3. Backups older than `BACKUP_KEEP_DAYS` (14) are deleted, but the newest `BACKUP_MIN_KEEP` (3)
   are always kept.
4. If `BACKUP_UPLOAD_COMMAND` is set, it runs with the backup folder as `$1`, for example:

   ```sh
   BACKUP_UPLOAD_COMMAND='aws s3 cp --recursive "$1" "s3://alakh-backups/$(basename "$1")"'
   ```

The service's healthcheck turns **unhealthy** when the last verified backup is older than two
intervals. Alert on it (for example `docker inspect --format '{{.State.Health.Status}}' alakh_backup`
in your monitoring).

CI runs the same scripts on every backend change (the **Backup & restore drill** job in
`backend-ci.yml`):
- It backs up two databases and verifies the backup.
- It deletes half the data, restores in place, and checks the data is identical.
- It checks that a tampered backup and an unconfirmed in-place restore are refused.

## Everyday commands

On a production server deployed with docs/DEPLOYMENT.md, use the matching `prod-` targets
(`make prod-backup`, `prod-verify-backup`, `prod-restore`, `prod-restore-in-place`): they read
`.env.production` and the production compose file. The commands below are for a development stack.

| Command | What it does |
|---|---|
| `make db-backup` | Back up now, then verify that backup |
| `make db-verify-backup [BACKUP=backups/<ts>]` | Prove a backup restores (latest by default) |
| `make db-restore BACKUP=backups/<ts> [DBS="booking_db"]` | Restore **next to** the live data as `<db>_restored`; nothing is overwritten |
| `make db-restore-in-place BACKUP=backups/<ts> [DBS=…]` | Replace live databases. It stops the services, restores, then restarts them |

## Recovering

**Someone deleted or broke some rows** (for example one shop's bookings):

1. `make db-restore BACKUP=backups/<ts before the mistake> DBS=booking_db`
2. Compare `booking_db_restored` with `booking_db` (`make db-shell DB=booking_db_restored`) and copy
   back only the rows you need, for example with `INSERT … SELECT` through `dblink`, or
   `pg_dump -t bookings --data-only` piped into psql.
3. Drop `booking_db_restored` when done.

**A database is lost or corrupt:** `make db-restore-in-place BACKUP=backups/<ts> DBS=booking_db`.

**The whole server is lost:**
1. Start a fresh stack with the same `.env`, and keep the services stopped (`docker compose up -d postgres`).
2. Copy a backup folder from off-site storage into `backups/`.
3. Restore the roles first if they matter to you: `psql -f backups/<ts>/globals.sql`.
4. Run `make db-restore-in-place BACKUP=backups/<ts>`.

Restores refuse to start if any checksum differs from the one recorded at backup time.

## How much can be lost (RPO) and how long it takes (RTO)

- **Daily logical backups:** you lose at most `BACKUP_INTERVAL_HOURS` of data. A restore takes
  minutes for databases of this size; time yours with `make db-verify-backup`, which does a full
  restore.
- **Point-in-time recovery (production):** for an RPO of seconds, run PostgreSQL with continuous WAL
  archiving. Either use a managed database (Amazon RDS, Cloud SQL, Azure Database for PostgreSQL;
  all offer PITR) or self-host with pgBackRest or WAL-G. Keep the daily logical backups anyway:
  they survive mistakes that are replicated everywhere, and they restore one database or one table
  on their own.

## Things to get right in production

- **Off-site and immutable:** send backups to another account or region (`BACKUP_UPLOAD_COMMAND`).
  Turn on object lock or versioning there, so ransomware or a bad command cannot delete them too.
- **Encryption:** dumps contain personal data (names, phone numbers, addresses). Store them on
  encrypted volumes or buckets (SSE-KMS or similar), and limit who can read them.
- **Redis** holds only short-lived state: rate-limit counters, sign-in lockouts, sign-out markers
  and OTP send limits. Losing it is safe; at worst a few signed-out access tokens work until they
  expire (30 minutes). It runs with AOF persistence anyway.
- **Drill:** once a quarter, restore the latest off-site backup onto a spare server and run the
  stack against it. The CI drill proves the scripts work; only a real drill proves your process does.
