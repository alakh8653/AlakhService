# AlakhService

[![Backend CI](https://github.com/alakh8653/AlakhService/actions/workflows/backend-ci.yml/badge.svg)](https://github.com/alakh8653/AlakhService/actions/workflows/backend-ci.yml)
[![Mobile CI](https://github.com/alakh8653/AlakhService/actions/workflows/mobile-ci.yml/badge.svg)](https://github.com/alakh8653/AlakhService/actions/workflows/mobile-ci.yml)
[![Web CI](https://github.com/alakh8653/AlakhService/actions/workflows/web-ci.yml/badge.svg)](https://github.com/alakh8653/AlakhService/actions/workflows/web-ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> A hyperlocal service marketplace: customers book shops and home-visit professionals, shops run
> their day from a dashboard, and an admin panel keeps the platform safe.

```
  Flutter app          Shop dashboard        Admin dashboard
  (customers, pros,    (React + TS)          (React + TS)
   shop owners)
        │                    │                     │
        └────────────────────┼─────────────────────┘
                             ▼
                   ┌───────────────────┐
                   │    API gateway    │  :3000  routing, JWT checks, rate limits,
                   │ (TypeScript/Exp.) │         circuit breaker, websockets
                   └─────────┬─────────┘
                             ▼
      15 Python / FastAPI services (one PostgreSQL database each)
      auth · user · shop · booking · payment · notification · tracking · queue
      analytics · dispute · trust_risk · admin · compliance · pricing · service_catalog
                             │
                ┌────────────┴────────────┐
                ▼                         ▼
           PostgreSQL 16               Redis 7
```

## Features

- **Booking:** slots, walk-in lines with a TV board, home visits with live tracking, rescheduling,
  waitlists, free fixes (rework), shared visits and SOS.
- **Payments:** Razorpay (UPI and cards), GST invoices, refunds by cancellation policy, tips,
  loyalty points, referrals, prepaid packages and shop payouts.
- **Shops:** onboarding with KYC documents and admin approval, hours, capacity, staff, services,
  reviews and work photos.
- **Trust and safety:** in-app chat with contact details hidden, masked calls, disputes, risk
  scoring and a contact-sharing watch list ([docs](docs/TRUST_AND_SAFETY.md)).
- **Notifications:** push (Firebase), SMS (MSG91 or Twilio), email and WhatsApp reports.
- **Compliance:** Terms acceptance, consent, data export and account deletion
  ([docs](docs/LEGAL_PAGES.md)).
- **Operations:** one-server production deploy with Caddy HTTPS, verified daily backups,
  Prometheus, Alertmanager, Grafana and blackbox checks ([docs](docs/DEPLOYMENT.md)).
- **Languages:** the app ships in English and Hindi.

## Tech stack

| Layer | Technology |
|---|---|
| Mobile | Flutter 3.x, Dart, BLoC, get_it, Dio, Google Maps, Firebase Messaging, Razorpay |
| Web dashboards | React 19, TypeScript, Vite, Redux Toolkit, React Hook Form + Zod, Tailwind CSS 4, Recharts |
| API gateway | Node.js, TypeScript, Express 5, Redis (rate limits and sign-out revocation) |
| Services | Python, FastAPI, Pydantic 2, SQLAlchemy 2 (async), Alembic |
| Data | PostgreSQL 16, Redis 7 |
| Auth | JWT (HS256) access and refresh tokens, bcrypt, OTP sign-in |
| Infrastructure | Docker Compose, Caddy, Prometheus, Alertmanager, Grafana |
| CI | GitHub Actions: backend, web, mobile, end-to-end, deploy checks, security scan, release |

## Quick start

```bash
git clone https://github.com/alakh8653/AlakhService.git
cd AlakhService
make setup   # .env, one virtualenv per service, npm ci, pre-commit
make dev     # the whole stack in Docker, with source mounts and auto-reload
make test    # Python and Node tests
```

`make help` lists every command.

## Deploy to production

One Linux server with Docker, automatic HTTPS (Caddy), daily verified backups and optional
monitoring. Step-by-step guide for non-experts, including the Android release:
**[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)**. Before launch, go through the
[launch checklist](docs/launch/LAUNCH_CHECKLIST.md).

```bash
cp .env.production.example .env.production   # fill it in
make prod-preflight                          # checks the file and the server
make prod-deploy                             # build, migrate, rolling restart, smoke test
```

## Development setup

### Prerequisites

- Docker ≥ 24 & Docker Compose ≥ 2.20
- Python 3.11+
- Node.js 20.19+ (22 LTS recommended)
- Flutter 3.x SDK (CI uses 3.47)
- `make` (optional but recommended)

### 1. Clone & configure

```bash
git clone https://github.com/alakh8653/AlakhService.git
cd AlakhService
cp .env.example .env
# Edit .env and fill in your real credentials
```

### 2. Start infrastructure + all services

```bash
docker compose up -d --build
# or, with source mounts + auto-reload:
make dev
```

Each service gets its own PostgreSQL database (see `infra/postgres/init-databases.sql`) and
applies its Alembic migrations on start-up.

**Database migrations** live in `services/<name>/migrations` (and `backend/migrations`):

```bash
make db-migrate                                              # all services
make db-new-migration SERVICE=auth_service NAME="add column" # after changing models (needs `make dev`)
make db-rollback SERVICE=auth_service
```

CI applies every service's migrations to PostgreSQL and fails if the models and migrations drift.

### 3. Verify services are healthy

```bash
curl http://localhost:3000/health          # API Gateway (apps use http://localhost:3000/api/v1)
curl http://localhost:8001/health          # Auth Service
curl http://localhost:8002/health          # User Service
curl http://localhost:8001/docs            # Interactive API docs (any service)
```

### 4. Run the checks locally (without Docker)

```bash
make setup-python setup-node   # one virtualenv per service + npm ci for both dashboards
make test-python test-node test-mobile
make lint-python lint-node
```

### 5. Mobile app (development)

```bash
cd apps/mobile_app
flutter pub get
dart run build_runner build   # generates test mocks
flutter test
flutter run                   # see android/README.md and ios/README.md for API keys
```

### 6. Web dashboards (development)

```bash
cd apps/admin_dashboard_web    # or apps/shop_dashboard_web
cp .env.example .env           # VITE_API_BASE_URL=http://localhost:3000/api/v1 (the gateway)
npm ci
npm run dev                    # shop: http://localhost:5173, admin: http://localhost:5174
```

### 7. Create the first admin

The admin dashboard only accepts admin accounts, and there is none by default. Register a normal
account first (in the shop dashboard, the mobile app or `POST /api/v1/auth/register`), then:

```bash
make make-admin ACCOUNT=you@example.com     # email or phone number; needs `make dev` running
make revoke-admin ACCOUNT=you@example.com   # back to a normal user
```

The account must sign in again for the change to take effect.

For a ready-made demo instead, `make db-seed` (with `make dev` running) adds `admin@example.com`
(already an admin), `owner@example.com` with a "Demo Salon" and three services, and
`customer@example.com` with one booking, all with the password `Demo-pass-1`. It is safe to re-run,
and refuses to run against anything but `localhost`.


## Microservices

| Service | Port | Description |
|---|---|---|
| `auth_service` | 8001 | Authentication, JWT issuance, OAuth 2.0 |
| `user_service` | 8002 | Customer & provider profile management |
| `shop_service` | 8003 | Shop/business registration and management |
| `booking_service` | 8004 | Service booking lifecycle |
| `payment_service` | 8005 | Payments, refunds, wallet, payouts |
| `notification_service` | 8006 | Push, SMS, email notifications |
| `tracking_service` | 8007 | Real-time GPS tracking |
| `queue_service` | 8008 | Job queue and priority scheduling |
| ~~`dispatch_service`~~ | — | Deprecated, not deployed ([DEPRECATED.md](services/dispatch_service/DEPRECATED.md)) |
| `analytics_service` | 8010 | Reporting, metrics, dashboards |
| `dispute_service` | 8011 | Dispute creation and mediation |
| `trust_risk_service` | 8012 | Fraud detection, KYC, risk scoring |
| `admin_service` | 8013 | Platform administration |
| `compliance_service` | 8014 | Regulatory compliance and audit |
| `pricing_engine` | 8015 | Dynamic pricing rules and computation |
| `service_catalog_service` | 8016 | Service definitions, variants, SKUs |
| ~~`catalog_service`~~ | — | Deprecated, not deployed; `service_catalog_service` is the catalogue ([DEPRECATED.md](services/catalog_service/DEPRECATED.md)) |
| `api_gateway` | 3000 | Single entry point: routing, JWT checks, rate limiting, circuit breaker ([docs](services/api_gateway/README.md)) |


## Directory structure

```
AlakhService/
├── apps/
│   ├── mobile_app/            # Flutter app for customers, professionals and shop owners
│   ├── shop_dashboard_web/    # React shop owner dashboard
│   └── admin_dashboard_web/   # React admin dashboard
├── services/
│   ├── api_gateway/           # TypeScript API gateway (the only public entry point)
│   └── <name>_service/        # 15 FastAPI services, each with app/, migrations/ and tests/
├── deploy/                    # Caddy, monitoring, and the public site with the legal pages
├── infra/postgres/            # Creates one database per service on first start
├── scripts/                   # Deploy, backup, seed, end-to-end and load-test scripts
├── docs/                      # Deployment, recovery, legal, trust and launch guides
├── backend/                   # Deprecated legacy monolith, unused (see backend/DEPRECATED.md)
├── docker-compose.yml         # Local stack
├── docker-compose.dev.yml     # Source mounts and auto-reload for `make dev`
└── docker-compose.prod.yml    # Production stack
```

## Documentation

| Guide | What it covers |
|---|---|
| [DEPLOYMENT.md](docs/DEPLOYMENT.md) | Going live on one server, step by step |
| [DISASTER_RECOVERY.md](docs/DISASTER_RECOVERY.md) | Backups, restores and what to do when data is lost |
| [LIVE_QUEUE.md](docs/LIVE_QUEUE.md) | Walk-in lines, the TV board and their capacity |
| [TRUST_AND_SAFETY.md](docs/TRUST_AND_SAFETY.md) | Start codes, free fixes, shared visits, SOS, verified badge |
| [PRIVACY_AND_CONTACT.md](docs/PRIVACY_AND_CONTACT.md) | How customers and shops talk without sharing numbers |
| [LEGAL_PAGES.md](docs/LEGAL_PAGES.md) | Legal pages, consent at sign-up, account deletion |
| [WHATSAPP_REPORTS.md](docs/WHATSAPP_REPORTS.md) | Reports sent to professionals on WhatsApp |
| [launch/](docs/launch/LAUNCH_CHECKLIST.md) | Launch checklist, staging, Play Store listing, shop owner guide |
| [PRODUCT_RESEARCH.md](docs/PRODUCT_RESEARCH.md) | What customers and providers need, what was added, what is next |
| [API gateway](services/api_gateway/README.md) | Route table, access rules, monitoring endpoints |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md). Report
security problems as described in [SECURITY.md](SECURITY.md).

## License

MIT, see [LICENSE](LICENSE).
