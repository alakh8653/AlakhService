# Contributing to AlakhService

Thanks for helping. This page is the short version of how work lands here.

## Before you start

- Set up once: `make setup` (creates `.env`, one virtualenv per service, `npm ci` for the gateway
  and both dashboards, and the pre-commit hooks). For the app: `make setup-mobile`.
- Run the stack: `make dev`. `make health` checks the gateway and every service.
- `make help` lists every command.

## Where code goes

| Change | Place |
|---|---|
| An API or business rule | the owning service in `services/<name>/` (see the table in the [README](README.md#microservices)) |
| A new public path | also `services/api_gateway/src/routes.ts`, with its access level |
| Mobile app | `apps/mobile_app/lib/features/<feature>/` (data, domain, presentation) |
| Dashboards | `apps/shop_dashboard_web/` or `apps/admin_dashboard_web/` |
| Deployment | `docker-compose.prod.yml`, `deploy/`, `scripts/deploy/`, and [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) |

Do not change `backend/`, `services/catalog_service/` or `services/dispatch_service/`: they are
deprecated and not deployed (see their `DEPRECATED.md`).

## Branches and commits

- Branch from `main`; the pre-commit hooks refuse commits made directly on `main`.
- Write [Conventional Commits](https://www.conventionalcommits.org/): `feat(booking): ...`,
  `fix(payment): ...`, `docs: ...`, `chore(deps): ...`. The changelog is generated from them
  (`cliff.toml`), so the subject is what users will read.
- One logical change per pull request. Fill in the PR template.

## Database changes

Every service owns its database and its Alembic migrations in `services/<name>/migrations`.
After changing a model:

```bash
make db-new-migration SERVICE=booking_service NAME="add reminder column"   # needs make dev
make db-migrate SERVICE=booking_service
```

Read the generated file before committing. CI applies every migration to PostgreSQL and fails if
the models and migrations drift.

## Checks to run before you push

```bash
make lint          # ruff, eslint, yamllint, hadolint
make test          # every Python service and the Node projects
make test-mobile   # if you touched apps/mobile_app
```

`make format` fixes most lint failures. CI runs the same checks plus an end-to-end flow, a
security scan and the deploy checks; a pull request merges only when they pass.

## Tests

- Python services: `pytest` in `services/<name>/tests/`. Add a test for every bug you fix.
- Gateway and dashboards: `npm test` (Vitest), next to the code in `test/` or `__tests__/`.
- Mobile: `flutter test`; mocks are generated with `dart run build_runner build`.

## Secrets and personal data

Never commit `.env` files, keys, `google-services.json` or real customer data. The
`detect-secrets` and `gitleaks` hooks catch most mistakes. Security problems go to the address in
[SECURITY.md](SECURITY.md), not to a public issue.

## Conduct

Everyone taking part follows the [Code of Conduct](CODE_OF_CONDUCT.md).
