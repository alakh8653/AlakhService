# AlakhService

[![Backend CI](https://github.com/alakh8653/AlakhService/actions/workflows/backend-ci.yml/badge.svg)](https://github.com/alakh8653/AlakhService/actions/workflows/backend-ci.yml)
[![Mobile CI](https://github.com/alakh8653/AlakhService/actions/workflows/mobile-ci.yml/badge.svg)](https://github.com/alakh8653/AlakhService/actions/workflows/mobile-ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> Enterprise-grade hyperlocal service marketplace — connecting customers with skilled service providers.

```
┌─────────────────────────────────────────────────────────────────────┐
│                      AlakhService Platform                          │
│                                                                     │
│  ┌──────────┐  ┌──────────────┐  ┌─────────────────────────────┐  │
│  │  Mobile  │  │  Shop Dash   │  │       Admin Dashboard        │  │
│  │  (Flutter│  │  (React/TS)  │  │        (React/TS)            │  │
│  └────┬─────┘  └──────┬───────┘  └──────────────┬──────────────┘  │
│       │               │                          │                  │
│       └───────────────┴──────────────────────────┘                 │
│                               │                                     │
│                    ┌──────────▼──────────┐                         │
│                    │     API Gateway      │                         │
│                    │  (TypeScript/Express)│                         │
│                    └──────────┬──────────┘                         │
│                               │                                     │
│    ┌──────────────────────────┼──────────────────────────┐         │
│    │           Microservices  │  (Python/FastAPI)         │         │
│    │  auth  user  shop  booking  payment  notification    │         │
│    │  queue  dispatch  tracking  pricing  search  ML      │         │
│    └──────────────────────────┬──────────────────────────┘         │
│                               │                                     │
│    ┌──────────────────────────▼──────────────────────────┐         │
│    │  PostgreSQL  Redis  Kafka  Elasticsearch  S3         │         │
│    └─────────────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────────────┘
```

## Features

- 🚀 **24 Python/FastAPI microservices** with async/await, Pydantic v2, SQLAlchemy 2.0
- 📱 **Flutter mobile app** with Clean Architecture, BLoC, offline-first
- 🌐 **2 React/TypeScript dashboards** (shop + admin) with real-time updates
- 🔀 **API Gateway** with circuit breaker, rate limiting, JWT validation
- 🤖 **ML Platform** — demand forecasting, dynamic pricing, fraud detection, recommendations
- 🔒 **Security** — JWT RS256, bcrypt, rate limiting, certificate pinning
- 📊 **Observability** — Prometheus, Grafana, Jaeger, structured logging
- 🏗️ **IaC** — Terraform + Kubernetes with HPA, PDB, network policies

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Mobile | Flutter 3.x, Dart, BLoC, GoRouter, Dio |
| Web | React 18, TypeScript, Redux Toolkit, React Query, Tailwind |
| API Gateway | TypeScript, Express, Redis |
| Backend | Python 3.11, FastAPI, SQLAlchemy 2.0, Celery |
| ML | scikit-learn, numpy, pandas, ARIMA, XGBoost |
| Data | PostgreSQL 15, Redis 7, Kafka, Elasticsearch 8 |
| Infra | Terraform, Kubernetes, Docker, GitHub Actions |

## Quick Start

```bash
# Clone and setup
git clone https://github.com/alakh8653/AlakhService.git
cd AlakhService
make setup

# Start all services
make dev

# Run tests
make test
```

## Project Structure

```
AlakhService/
├── apps/
│   ├── mobile_app/          # Flutter mobile app
│   ├── shop_dashboard_web/  # React shop owner dashboard
│   └── admin_dashboard_web/ # React admin dashboard
├── services/
│   ├── api_gateway/         # TypeScript API gateway
│   ├── auth_service/        # Authentication & authorization
│   ├── booking_service/     # Booking FSM & management
│   ├── payment_service/     # Payments & ledger
│   └── ...                  # 20+ more microservices
├── packages/                # Shared Python SDKs
├── services/ml_platform/    # ML models & inference
├── infra/                   # Terraform & Kubernetes
├── docs/                    # Documentation
└── scripts/                 # Utility scripts
```

## Contributing

See [CONTRIBUTING.md](docs/onboarding/contributing.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## License

MIT — see [LICENSE](LICENSE).