# Deprecated: `catalog_service`

This service is **not deployed and not used** by anything else in AlakhService.

- No other service, app or dashboard calls it. The catalogue the apps browse and the booking flow
  reads (services, prices, durations) is `service_catalog_service` (`SERVICE_CATALOG_URL`,
  `/api/v1/categories` and `/api/v1/services`). Nothing routes `/api/v1/catalog` any more.
- It has been removed from `docker-compose.yml`, `docker-compose.prod.yml`, `docker-compose.dev.yml`,
  the API gateway (`services/api_gateway/src/routes.ts` and `config.ts`), the CI test matrix,
  the Prometheus probes and `scripts/deploy/deploy.sh`.
- The source is kept for reference only. Do not add features here.

An existing server keeps its old `catalog_db` database (created by `infra/postgres/init-databases.sql`
and backed up like every other database) and Redis database 16. No other service reads them; drop the
database once you are sure nothing was ever written to it.

To bring the service back, re-add it to the compose files, the gateway, the CI matrix and monitoring.
