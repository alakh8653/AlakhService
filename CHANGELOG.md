# Changelog

All notable changes to AlakhService will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Types of changes:
- **Added** — for new features.
- **Changed** — for changes in existing functionality.
- **Deprecated** — for soon-to-be removed features.
- **Removed** — for now removed features.
- **Fixed** — for any bug fixes.
- **Security** — in case of vulnerabilities.

---

## [Unreleased]

### Added

- Comprehensive root configuration files (.gitignore, .editorconfig, .prettierrc,
  .eslintrc.json, .pre-commit-config.yaml, .env.example, Makefile)
- Full docker-compose.yml with all microservices, health checks, networks, and volumes
- docker-compose.dev.yml with hot-reload and debug overrides
- README.md with architecture diagram, badges, and quick-start guide
- SECURITY.md with vulnerability reporting process
- CODE_OF_CONDUCT.md (Contributor Covenant v2.1)
- LICENSE (MIT)

---

## [1.0.0] — 2024-01-15

### Added

- **API Gateway** — FastAPI-based reverse proxy with JWT verification, rate
  limiting, CORS, and request tracing (OpenTelemetry).
- **Auth Service** — Authentication microservice supporting:
  - Email/password with bcrypt hashing.
  - OAuth2 (Google, GitHub, Facebook, Apple).
  - Multi-factor authentication (TOTP via `pyotp`, FIDO2 via `fido2`).
  - JWT access tokens (15 min) + refresh tokens (30 days, rotating).
  - Forgot-password and email verification flows.
- **User Service** — Profile management, avatar upload to S3/MinIO,
  address book, preferences, and account deletion (GDPR).
- **Shop Service** — Product catalogue with Elasticsearch full-text search,
  category hierarchy, inventory management, and image gallery.
- **Booking Service** — Appointment and reservation system with real-time
  availability, conflict detection, and iCalendar (ICS) export.
- **Payment Service** — Multi-gateway payments (Stripe, PayPal, Razorpay),
  refunds, invoices, tax calculation, and PCI-DSS compliant card data handling.
- **Notification Service** — Unified email (SendGrid), SMS (Twilio), and push
  (FCM/APNs) notifications with template management and delivery receipts.
- **Tracking Service** — Real-time order and delivery tracking via Kafka event
  streams, WebSocket connections, and geospatial queries (PostGIS).
- **Flutter Mobile App** — iOS and Android app with:
  - BLoC state management.
  - Offline-first architecture (Drift/Hive local storage).
  - Biometric authentication.
  - Push notifications.
  - Deep linking.
- **React Web Dashboard** — Admin dashboard built with Next.js 14, Tailwind
  CSS, and shadcn/ui components.
- **PostgreSQL** databases (one per service) with full migration support
  (Alembic).
- **Redis** for session storage, caching, and rate limiting.
- **Apache Kafka** for asynchronous event streaming between services.
- **Elasticsearch** for product and user search.
- **MinIO** for local S3-compatible object storage.
- **Prometheus** metrics exposed from every service.
- **Grafana** dashboards pre-configured for all services.
- **Jaeger** distributed tracing via OpenTelemetry.
- **GitHub Actions** CI/CD pipelines:
  - Lint, test, security scan on every PR.
  - Docker image build + push on merge to `main`.
  - Automatic deployment to staging; manual promotion to production.
- **Terraform** modules for AWS EKS deployment.
- **Helm chart** for Kubernetes deployment.
- Comprehensive unit and integration test suites (≥ 80 % coverage).
- OpenAPI 3.1 specification for all services, with generated TypeScript clients.
- gRPC definitions for inter-service communication.
- Structured JSON logging with correlation IDs.
- Sentry error tracking integration.

### Changed

- N/A (initial release)

### Fixed

- N/A (initial release)

---

## [0.9.0-beta] — 2023-11-20

### Added

- Initial beta release for internal testing.
- Core auth and user services.
- Basic API gateway with JWT verification.
- Docker Compose development environment.

### Fixed

- JWT expiry not honoured for refresh tokens.
- CORS headers missing on error responses.

---

## [0.1.0-alpha] — 2023-09-01

### Added

- Project scaffolding.
- Repository structure for monorepo with services, mobile, web, and infra.
- Base Dockerfile templates.
- Initial CI workflow.

---

[Unreleased]: https://github.com/AlakhService/AlakhService/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/AlakhService/AlakhService/compare/v0.9.0-beta...v1.0.0
[0.9.0-beta]: https://github.com/AlakhService/AlakhService/compare/v0.1.0-alpha...v0.9.0-beta
[0.1.0-alpha]: https://github.com/AlakhService/AlakhService/releases/tag/v0.1.0-alpha
