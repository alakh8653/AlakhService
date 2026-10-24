# Deprecated: `dispatch_service`

This service is **not deployed and not used** by anything else in AlakhService.

- No other service, app or dashboard calls it. Shops assign their own staff to a booking in
  booking_service (`POST /api/v1/bookings/{id}/assign`); nothing routes `/api/v1/dispatch` or
  `/api/v1/providers` any more.
- It has been removed from `docker-compose.yml`, `docker-compose.prod.yml`, `docker-compose.dev.yml`,
  the API gateway (`services/api_gateway/src/routes.ts` and `config.ts`), the CI test matrix,
  the Prometheus probes and `scripts/deploy/deploy.sh`.
- The source is kept for reference only. Do not add features here.

An existing server keeps its old `dispatch_db` database (created by `infra/postgres/init-databases.sql`
and backed up like every other database). No other service reads it; drop it once you are sure
nothing was ever written to it.

To bring the service back, re-add it to the compose files, the gateway, the CI matrix and monitoring.
