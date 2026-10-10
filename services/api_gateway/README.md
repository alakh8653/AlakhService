# API Gateway

Single entry point for the AlakhService apps (`http://localhost:3000/api/v1`). It routes each
request to the service that owns the path, verifies access tokens, rate-limits clients, and stops
calling services that keep failing.

## Run

```bash
npm ci
SECRET_KEY=dev-secret npm run dev      # http://localhost:3000, hot reload
npm test                               # vitest (routes, auth, proxying, circuit breaker, rate limit)
npm run lint && npm run type-check && npm run build
```

Under Docker Compose it runs as `api_gateway` on port 3000.

## Routing

Every service mounts its API under `/api/v1`, and each top-level path segment belongs to one
service, so the gateway forwards by longest matching prefix (see `src/routes.ts`):

| Path prefix (`/api/v1/…`) | Service |
|---|---|
| `auth` | auth_service |
| `users` | user_service |
| `shops` | shop_service |
| `bookings` | booking_service |
| `payments`, `accounts`, `webhooks` | payment_service |
| `notifications` | notification_service |
| `locations`, `geofences` | tracking_service |
| `queues` | queue_service |
| `dispatch`, `providers` | dispatch_service |
| `events`, `metrics`, `funnels`, `cohorts` | analytics_service |
| `disputes` | dispute_service |
| `risk` | trust_risk_service |
| `admin`, `audit-logs`, `system-config` | admin_service |
| `consent`, `gdpr` | compliance_service |
| `pricing`, `coupons` | pricing_engine |
| `categories`, `services` | service_catalog_service |
| `catalog` | catalog_service |

Admin dashboard paths are mapped onto the owning services: `admin/audit-logs` → admin_service
`audit-logs`, `admin/disputes` → dispute_service `disputes`. `admin/monitoring/health` is answered
by the gateway itself with the health of every service. Dashboard endpoints that no service
implements yet (`admin/finance`, `admin/monitoring/metrics`, `admin/access`) return `501`.

## Access

Tokens are the HS256 access tokens issued by auth_service, verified with the shared `SECRET_KEY`.
Refresh tokens and single-purpose tokens (password reset) are rejected.

- **Public:** sign-in, registration, token refresh, OTP and password recovery; payment webhooks
  (verified by signature in payment_service); `GET` on `shops`, `categories`, `services`, `catalog`.
- **Admin role:** `admin/*`, `audit-logs`, `system-config`, `risk`, and analytics reporting.
- **Everything else:** any signed-in user. Services still check the token themselves.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `SECRET_KEY` (or `JWT_SECRET_KEY`) | — (required) | Key that verifies access tokens; same value as the services |
| `PORT` | `3000` | Listen port |
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:5174` | Comma-separated allowed origins |
| `RATE_LIMIT_WINDOW_MS` / `RATE_LIMIT_MAX` | `60000` / `300` | Requests per client per window on `/api` |
| `UPSTREAM_TIMEOUT_MS` | `15000` | Timeout per proxied request (504 when exceeded) |
| `BREAKER_FAILURE_THRESHOLD` / `BREAKER_RESET_TIMEOUT_MS` | `5` / `30000` | Consecutive failures (errors or 5xx) that open a service's circuit, and how long it stays open (503) |
| `<NAME>_SERVICE_URL`, `PRICING_ENGINE_URL`, `SERVICE_CATALOG_URL` | `http://<service>:8000` | Upstream base URLs |

Each request gets an `x-request-id` (an incoming one is kept), forwarded to the service and logged
as one JSON line with method, path, status, duration and upstream.
