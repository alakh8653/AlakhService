
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

# AlakhService — Enterprise-Grade Full-Stack Service Platform

[![Build Status](https://img.shields.io/badge/build-passing-brightgreen?style=flat-square)](https://github.com/AlakhService/AlakhService/actions)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](./LICENSE)
[![Coverage](https://img.shields.io/badge/coverage-85%25-green?style=flat-square)](./coverage)
[![Python](https://img.shields.io/badge/python-3.11-blue?style=flat-square)](https://python.org)
[![Flutter](https://img.shields.io/badge/flutter-3.x-02569B?style=flat-square)](https://flutter.dev)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688?style=flat-square)](https://fastapi.tiangolo.com)

> A production-ready, microservices-based platform for on-demand service booking — connecting customers, service providers, and shop owners through a unified ecosystem of mobile apps, web dashboards, and intelligent backend services.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐  │
│  │  Flutter Mobile  │  │  React Customer  │  │   React Admin/Shop   │  │
│  │  (Customer App)  │  │   Web Dashboard  │  │      Dashboard       │  │
│  └────────┬─────────┘  └────────┬─────────┘  └──────────┬───────────┘  │
└───────────┼─────────────────────┼───────────────────────┼──────────────┘
            │                     │                       │
            └─────────────────────▼───────────────────────┘
                          ┌───────────────┐
                          │  API Gateway  │  :3000
                          │   (Node.js)   │
                          └───────┬───────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          │                       │                       │
  ┌───────▼───────┐     ┌─────────▼───────┐     ┌────────▼────────┐
  │  Auth Service │     │  User Service   │     │  Shop Service   │
  │    :8001      │     │    :8002        │     │    :8003        │
  └───────────────┘     └─────────────────┘     └─────────────────┘
          │                       │                       │
  ┌───────▼───────┐     ┌─────────▼───────┐     ┌────────▼────────┐
  │ Booking Svc   │     │ Payment Service │     │Notification Svc │
  │    :8004      │     │    :8005        │     │    :8006        │
  └───────────────┘     └─────────────────┘     └─────────────────┘
          │
  ┌───────▼──────────────────────────────────────────────────────┐
  │                     EVENT BUS (Kafka)                        │
  └───────┬──────────────────────────────────────────────────────┘
          │
  ┌───────▼──────────────────────────────────────────────────────┐
  │                   DATA LAYER                                 │
  │   PostgreSQL  │  Redis Cache  │  S3 Object Store             │
  └──────────────────────────────────────────────────────────────┘
```

---

## ✨ Features

- **18+ Microservices** — Independently deployable services covering every business domain
- **Flutter Mobile App** — Cross-platform (iOS/Android) customer-facing application
- **React Dashboards** — Admin, Shop Owner, and Analytics web portals
- **ML Platform** — Intelligent demand forecasting, dynamic pricing, and fraud detection
- **Real-Time Tracking** — Live GPS tracking for field technicians and delivery agents
- **Smart Dispatch** — Automated job assignment based on proximity, skill, and availability
- **Dynamic Pricing Engine** — Time-based, demand-aware pricing with configurable rules
- **Trust & Risk Engine** — Automated KYC, background checks, and fraud scoring
- **Compliance Service** — Automated regulatory checks and audit trail management
- **Kafka Event Streaming** — Fully event-driven architecture with guaranteed delivery
- **Service Catalog** — Structured service definitions with variants and pricing tiers
- **Dispute Resolution** — Mediated dispute workflow with evidence management
- **Queue Management** — Configurable waiting queues with priority scheduling
- **Push / SMS / Email Notifications** — Omnichannel notification delivery
- **Kubernetes-Ready** — Helm charts and Kubernetes manifests included
- **Terraform Infrastructure** — One-command cloud provisioning for AWS/GCP
- **Observability** — Distributed tracing with Jaeger, metrics with Prometheus/Grafana
- **CI/CD Pipelines** — GitHub Actions for backend, mobile, and web

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| **Mobile** | Flutter 3.x / Dart |
| **Backend** | FastAPI / Python 3.11 |
| **API Gateway** | Node.js / Express |
| **Web (Customer)** | React 18 / TypeScript / Vite |
| **Web (Admin)** | React 18 / TypeScript / Ant Design |
| **Database** | PostgreSQL 15 |
| **Cache** | Redis 7 |
| **Message Bus** | Apache Kafka |
| **Search** | Elasticsearch |
| **Object Storage** | AWS S3 |
| **Auth** | JWT + OAuth 2.0 |
| **Containerisation** | Docker / Docker Compose |
| **Orchestration** | Kubernetes + Helm |
| **Infrastructure** | Terraform (AWS) |
| **Monitoring** | Prometheus + Grafana |
| **Tracing** | Jaeger |
| **Error Tracking** | Sentry |
| **CI/CD** | GitHub Actions |

---

## 🚀 Quick Setup

### Prerequisites

- Docker ≥ 24 & Docker Compose ≥ 2.20
- Python 3.11+
- Node.js 18+
- Flutter 3.x SDK
- `make` (optional but recommended)

### 1. Clone & configure

```bash
git clone https://github.com/AlakhService/AlakhService.git
cd AlakhService
cp .env.example .env
# Edit .env and fill in your real credentials
```

### 2. Start infrastructure + all services

```bash
docker compose up -d
```

### 3. Run database migrations (first run)

```bash
docker compose exec auth_service alembic upgrade head
docker compose exec user_service alembic upgrade head
# Repeat for other services that own a DB schema
```

### 4. Verify services are healthy

```bash
curl http://localhost:3000/health          # API Gateway
curl http://localhost:8001/health          # Auth Service
curl http://localhost:8002/health          # User Service
```

### 5. Mobile app (development)

```bash
cd apps/mobile_app
flutter pub get
flutter run
```

### 6. Web dashboard (development)

```bash
cd apps/admin_web
npm ci
npm run dev
```

---

## 🧩 Microservices

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
| `dispatch_service` | 8009 | Automated job assignment and routing |
| `analytics_service` | 8010 | Reporting, metrics, dashboards |
| `dispute_service` | 8011 | Dispute creation and mediation |
| `trust_risk_service` | 8012 | Fraud detection, KYC, risk scoring |
| `admin_service` | 8013 | Platform administration |
| `compliance_service` | 8014 | Regulatory compliance and audit |
| `pricing_engine` | 8015 | Dynamic pricing rules and computation |
| `service_catalog_service` | 8016 | Service definitions, variants, SKUs |
| `ml_platform` | 8017 | ML models: demand forecast, pricing, fraud |
| `api_gateway` | 3000 | Unified API entry point, auth middleware |

---

## 📁 Directory Structure


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

│   ├── mobile_app/              # Flutter customer app
│   ├── admin_web/               # React admin dashboard
│   └── customer_web/            # React customer web portal
├── services/
│   ├── auth_service/            # FastAPI — authentication
│   ├── user_service/            # FastAPI — users
│   ├── shop_service/            # FastAPI — shops
│   ├── booking_service/         # FastAPI — bookings
│   ├── payment_service/         # FastAPI — payments
│   ├── notification_service/    # FastAPI — notifications
│   ├── tracking_service/        # FastAPI — GPS tracking
│   ├── queue_service/           # FastAPI — job queues
│   ├── dispatch_service/        # FastAPI — dispatch logic
│   ├── analytics_service/       # FastAPI — analytics
│   ├── dispute_service/         # FastAPI — disputes
│   ├── trust_risk_service/      # FastAPI — trust & risk
│   ├── admin_service/           # FastAPI — admin
│   ├── compliance_service/      # FastAPI — compliance
│   ├── pricing_engine/          # FastAPI — pricing
│   ├── service_catalog_service/ # FastAPI — catalog
│   └── ml_platform/             # Python — ML models & serving
├── gateway/                     # Node.js API Gateway
├── infra/
│   ├── terraform/               # AWS infrastructure as code
│   ├── kubernetes/              # K8s manifests
│   └── helm/                    # Helm charts
├── scripts/                     # Utility & migration scripts
├── docs/                        # Architecture & API documentation
├── .github/
│   ├── workflows/               # CI/CD pipelines
│   ├── ISSUE_TEMPLATE/          # Issue templates
│   └── PULL_REQUEST_TEMPLATE.md
├── docker-compose.yml
├── .env.example
├── .gitignore
├── LICENSE
└── README.md
```

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/my-feature`
3. Commit your changes following [Conventional Commits](https://www.conventionalcommits.org/)
4. Push to your fork and open a Pull Request against `develop`
5. Fill in the PR template and ensure all CI checks pass

Please read [CONTRIBUTING.md](./docs/CONTRIBUTING.md) for detailed guidelines on code style, testing requirements, and the review process.

---

## 📄 License

Copyright © 2024 AlakhService Contributors. Released under the [MIT License](./LICENSE).

