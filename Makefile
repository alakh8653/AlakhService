# =============================================================================
# AlakhService – Makefile
# =============================================================================
# Usage: make <target>
# Run `make help` to list all available targets.
# =============================================================================

SHELL := /bin/bash
.ONESHELL:
# Each recipe runs in one shell (.ONESHELL); stop at the first failing command so a
# failed lint/scan is not reported as passed by the success line that follows it.
.SHELLFLAGS := -e -o pipefail -c
.DEFAULT_GOAL := help

# ── Project metadata ──────────────────────────────────────────────────────────
PROJECT      := alakhservice
VERSION      := $(shell git describe --tags --always --dirty 2>/dev/null || echo "dev")
COMMIT       := $(shell git rev-parse --short HEAD 2>/dev/null || echo "none")
BUILD_DATE   := $(shell date -u +"%Y-%m-%dT%H:%M:%SZ")
REGISTRY     := ghcr.io/alakhservice
DOCKER_TAG   ?= $(VERSION)

# ── Directories ───────────────────────────────────────────────────────────────
ROOT_DIR     := $(shell pwd)
SERVICES_DIR := $(ROOT_DIR)/services
MOBILE_DIR   := $(ROOT_DIR)/apps/mobile_app
WEB_APPS     := $(ROOT_DIR)/apps/admin_dashboard_web $(ROOT_DIR)/apps/shop_dashboard_web
NODE_PROJECTS := $(WEB_APPS) $(SERVICES_DIR)/api_gateway
PY_PROJECTS  := $(wildcard $(SERVICES_DIR)/*/requirements.txt) $(ROOT_DIR)/backend/requirements.txt
SCRIPTS_DIR  := $(ROOT_DIR)/scripts

# ── Python settings ───────────────────────────────────────────────────────────
PYTHON       := python3.11
VENV         := .venv
PIP          := $(VENV)/bin/pip
PYTHON_VENV  := $(VENV)/bin/python

# ── Node settings ─────────────────────────────────────────────────────────────
NODE         := node
NPM          := npm

# ── Colors ────────────────────────────────────────────────────────────────────
RESET  := \033[0m
BOLD   := \033[1m
GREEN  := \033[32m
YELLOW := \033[33m
CYAN   := \033[36m
RED    := \033[31m

# ── Helpers ───────────────────────────────────────────────────────────────────
define log
	@printf "$(BOLD)$(CYAN)[$(PROJECT)]$(RESET) %s\n" $(1)
endef

define success
	@printf "$(BOLD)$(GREEN)✓ %s$(RESET)\n" $(1)
endef

define warn
	@printf "$(BOLD)$(YELLOW)⚠ %s$(RESET)\n" $(1)
endef

define error
	@printf "$(BOLD)$(RED)✗ %s$(RESET)\n" $(1)
endef

# =============================================================================
# HELP
# =============================================================================

.PHONY: help
help: ## Show this help message
	@printf "$(BOLD)$(CYAN)\n"
	@printf "  ╔═══════════════════════════════════════════╗\n"
	@printf "  ║         AlakhService Makefile             ║\n"
	@printf "  ╚═══════════════════════════════════════════╝\n"
	@printf "$(RESET)\n"
	@grep -E '^[a-zA-Z_/-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-35s$(RESET) %s\n", $$1, $$2}' \
		| sort
	@printf "\n"

# =============================================================================
# SETUP & INSTALLATION
# =============================================================================

.PHONY: setup
setup: setup-env setup-python setup-node setup-pre-commit ## Full project setup (run once)
	$(call success,"Setup complete! Run 'make dev' to start development.")

.PHONY: setup-env
setup-env: ## Copy .env.example to .env if .env does not exist
	$(call log,"Setting up environment variables...")
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		printf "$(YELLOW)  .env created from .env.example — fill in your secrets!$(RESET)\n"; \
	else \
		printf "  .env already exists, skipping.\n"; \
	fi

.PHONY: setup-python
setup-python: ## Create virtualenv and install all Python dependencies
	$(call log,"Setting up Python environment...")
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip setuptools wheel
	@if [ -f requirements.txt ]; then $(PIP) install -r requirements.txt; fi
	@if [ -f requirements-dev.txt ]; then $(PIP) install -r requirements-dev.txt; fi
	$(PIP) install ruff==0.17.1 pre-commit yamllint "bandit[toml]"  # ruff: same version as CI and pre-commit
	@# Services pin different library versions, so each one gets its own virtualenv.
	@for req in $(PY_PROJECTS); do \
		dir=$$(dirname "$$req"); \
		echo "→ $$dir"; \
		$(PYTHON) -m venv "$$dir/.venv" && \
		"$$dir/.venv/bin/pip" install -q -r "$$req" pytest pytest-asyncio pytest-cov httpx aiosqlite || exit 1; \
	done
	$(call success,"Python environment ready")

.PHONY: setup-node
setup-node: ## Install Node.js dependencies
	$(call log,"Installing Node.js dependencies...")
	@for app in $(NODE_PROJECTS); do \
		echo "→ $$app"; \
		(cd "$$app" && $(NPM) ci) || exit 1; \
	done
	$(call success,"Node dependencies installed")

.PHONY: setup-pre-commit
setup-pre-commit: ## Install pre-commit hooks
	$(call log,"Installing pre-commit hooks...")
	$(VENV)/bin/pre-commit install --install-hooks
	$(VENV)/bin/pre-commit install --hook-type commit-msg
	$(call success,"Pre-commit hooks installed")

.PHONY: setup-mobile
setup-mobile: ## Setup Flutter mobile dependencies
	$(call log,"Setting up Flutter dependencies...")
	cd $(MOBILE_DIR) && flutter pub get
	$(call success,"Flutter dependencies installed")

# =============================================================================
# DEVELOPMENT
# =============================================================================

.PHONY: dev
dev: ## Start all services in development mode (docker-compose)
	$(call log,"Starting development environment...")
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build

.PHONY: dev-backend
dev-backend: ## Start only backend services (no mobile/web)
	$(call log,"Starting backend services...")
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build

.PHONY: dev-infra
dev-infra: ## Start only infrastructure services (postgres, redis)
	$(call log,"Starting infrastructure services...")
	docker compose up -d postgres redis

.PHONY: dev-web
dev-web: ## Start a web dashboard in dev mode: make dev-web APP=admin_dashboard_web
	$(call log,"Starting web dev server...")
	cd $(ROOT_DIR)/apps/$(or $(APP),shop_dashboard_web) && $(NPM) run dev

.PHONY: dev-mobile
dev-mobile: ## Start Flutter mobile app (requires connected device/emulator)
	$(call log,"Starting Flutter app...")
	cd $(MOBILE_DIR) && flutter run

.PHONY: stop
stop: ## Stop all Docker services
	$(call log,"Stopping services...")
	docker compose -f docker-compose.yml -f docker-compose.dev.yml down
	$(call success,"Services stopped")

.PHONY: restart
restart: stop dev ## Restart all services

.PHONY: logs
logs: ## Follow logs from all services
	docker compose logs -f --tail=100

.PHONY: logs/%
logs/%: ## Follow logs for a specific service: make logs/auth_service
	docker compose logs -f --tail=200 $*

.PHONY: shell/%
shell/%: ## Open a shell in a running service: make shell/api_gateway
	docker compose exec $* /bin/sh

# =============================================================================
# TESTING
# =============================================================================

.PHONY: test
test: test-python test-node ## Run all tests

.PHONY: test-python
test-python: ## Run all Python tests with coverage
	$(call log,"Running Python tests...")
	@# Every service has its own top-level `app` package, so each suite runs in its own process/venv.
	@failed=""; \
	for req in $(PY_PROJECTS); do \
		dir=$$(dirname "$$req"); \
		echo "→ $$dir"; \
		(cd "$$dir" && .venv/bin/python -m pytest tests/ -q --cov=app --cov-report=term-missing:skip-covered) || failed="$$failed $$dir"; \
	done; \
	if [ -n "$$failed" ]; then echo "Failed:$$failed"; exit 1; fi
	$(call success,"Python tests passed")

.PHONY: test-node
test-node: ## Run all Node/TypeScript tests with coverage
	$(call log,"Running TypeScript tests...")
	@for app in $(NODE_PROJECTS); do \
		echo "→ $$app"; \
		(cd "$$app" && $(NPM) test -- --coverage) || exit 1; \
	done
	$(call success,"TypeScript tests passed")

.PHONY: test-mobile
test-mobile: ## Run Flutter widget and unit tests
	$(call log,"Running Flutter tests...")
	cd $(MOBILE_DIR) && flutter pub get && dart run build_runner build && flutter test --coverage
	$(call success,"Flutter tests passed")

.PHONY: test-security
test-security: ## Run security scans (bandit + npm audit)
	$(call log,"Running security scans...")
	$(VENV)/bin/bandit -q -r $(SERVICES_DIR) $(ROOT_DIR)/backend -x "*/tests/*,*/node_modules/*,*/.venv/*" \
		--severity-level medium --confidence-level medium
	@for app in $(NODE_PROJECTS); do \
		echo "→ $$app"; \
		(cd "$$app" && $(NPM) audit --omit=dev --audit-level=high) || exit 1; \
	done
	$(call success,"Security scan complete")

# =============================================================================
# LINTING & FORMATTING
# =============================================================================

.PHONY: lint
lint: lint-python lint-node lint-yaml lint-docker ## Run all linters

.PHONY: lint-python
lint-python: ## Lint Python code with Ruff
	$(call log,"Linting Python...")
	$(VENV)/bin/ruff check $(SERVICES_DIR) $(ROOT_DIR)/backend
	$(call success,"Python lint passed")

.PHONY: lint-node
lint-node: ## Lint TypeScript/JavaScript with ESLint
	$(call log,"Linting TypeScript...")
	@for app in $(NODE_PROJECTS); do \
		echo "→ $$app"; \
		(cd "$$app" && $(NPM) run lint && $(NPM) run type-check) || exit 1; \
	done
	$(call success,"TypeScript lint passed")

.PHONY: lint-yaml
lint-yaml: ## Lint YAML files with yamllint (config: .yamllint.yml)
	$(call log,"Linting YAML...")
	$(VENV)/bin/yamllint -c .yamllint.yml .
	$(call success,"YAML lint passed")

.PHONY: lint-docker
lint-docker: ## Lint Dockerfiles with hadolint (skipped if hadolint is not installed)
	$(call log,"Linting Dockerfiles...")
	@if ! command -v hadolint >/dev/null 2>&1; then \
		printf "$(BOLD)$(YELLOW)⚠ %s$(RESET)\n" "hadolint not installed, skipping (https://github.com/hadolint/hadolint)"; \
		exit 0; \
	fi; \
	find . -name "Dockerfile*" -not -path "*/node_modules/*" -print0 \
		| xargs -0 hadolint --ignore DL3008 --ignore DL3013 --ignore DL3018
	$(call success,"Dockerfile lint done")

.PHONY: format
format: format-python format-node ## Auto-format all code

.PHONY: format-python
format-python: ## Format Python code with Ruff (config: ruff.toml)
	$(call log,"Formatting Python...")
	$(VENV)/bin/ruff format $(SERVICES_DIR) $(ROOT_DIR)/backend
	$(VENV)/bin/ruff check --fix $(SERVICES_DIR) $(ROOT_DIR)/backend
	$(call success,"Python formatted")

.PHONY: format-node
format-node: ## Format TypeScript/JavaScript/CSS with Prettier
	$(call log,"Formatting TypeScript...")
	# No project lists prettier as a dependency, so run a pinned copy with the root .prettierrc.
	for app in $(NODE_PROJECTS); do \
		echo "→ $$app"; \
		(cd "$$app" && npx --yes prettier@3.6.2 --write src) || exit 1; \
	done
	$(call success,"TypeScript/CSS formatted")

.PHONY: format-mobile
format-mobile: ## Format Dart code
	$(call log,"Formatting Dart...")
	cd $(MOBILE_DIR) && dart format .
	$(call success,"Dart formatted")

# =============================================================================
# DATABASE
# =============================================================================

# Each service owns its database and Alembic migrations (services/<name>/migrations).
# These targets run inside the service containers started by `make dev` / `docker compose up`.
COMPOSE_DEV     := docker compose -f docker-compose.yml -f docker-compose.dev.yml
DB_SERVICES     := $(notdir $(patsubst %/,%,$(dir $(wildcard $(SERVICES_DIR)/*/alembic.ini))))

.PHONY: db-migrate
db-migrate: ## Apply pending migrations for every service (or one: make db-migrate SERVICE=auth_service)
	$(call log,"Applying database migrations...")
	@for svc in $(or $(SERVICE),$(DB_SERVICES)); do \
		echo "→ $$svc"; \
		docker compose exec -T $$svc alembic upgrade head || exit 1; \
	done
	$(call success,"Migrations applied")

.PHONY: db-rollback
db-rollback: ## Roll back the last migration of one service: make db-rollback SERVICE=auth_service
	@test -n "$(SERVICE)" || { echo "SERVICE is required, e.g. make db-rollback SERVICE=auth_service"; exit 1; }
	docker compose exec -T $(SERVICE) alembic downgrade -1
	$(call warn,"Rolled back 1 migration for $(SERVICE)")

.PHONY: db-new-migration
db-new-migration: ## Autogenerate a migration (needs make dev): make db-new-migration SERVICE=auth_service NAME="add column"
	@test -n "$(SERVICE)" -a -n "$(NAME)" || { echo "SERVICE and NAME are required"; exit 1; }
	$(call log,"Creating migration for $(SERVICE): $(NAME)...")
	$(COMPOSE_DEV) exec -T $(SERVICE) alembic revision --autogenerate -m "$(NAME)"
	$(call success,"Migration written to services/$(SERVICE)/migrations/versions")

.PHONY: db-seed
db-seed: ## Seed databases with development data (scripts/seed_database.py)
	@if [ -f $(SCRIPTS_DIR)/seed_database.py ]; then \
		$(PYTHON_VENV) $(SCRIPTS_DIR)/seed_database.py; \
	else \
		echo "No seed script yet (expected $(SCRIPTS_DIR)/seed_database.py)"; \
	fi

.PHONY: db-reset
db-reset: ## Drop all service databases and re-run migrations (DESTRUCTIVE)
	$(call warn,"This will DESTROY all local data. Press Ctrl-C to cancel...")
	@sleep 3
	$(call log,"Resetting databases...")
	docker compose down -v
	docker compose up -d --build
	$(call success,"Databases recreated; services re-apply migrations on start")

.PHONY: db-shell
db-shell: ## Open a psql shell: make db-shell DB=auth_db
	docker compose exec -e DB=$(DB) postgres sh -c 'psql -U "$$POSTGRES_USER" "$${DB:-$$POSTGRES_DB}"'

.PHONY: make-admin
make-admin: ## Grant admin access to a registered account: make make-admin ACCOUNT=you@example.com
	@test -n "$$ACCOUNT" || { echo "Usage: make make-admin ACCOUNT=<email or phone>"; exit 1; }
	docker compose exec -T auth_service python -m app.cli make-admin "$$ACCOUNT"

.PHONY: revoke-admin
revoke-admin: ## Return an admin to a normal user: make revoke-admin ACCOUNT=you@example.com
	@test -n "$$ACCOUNT" || { echo "Usage: make revoke-admin ACCOUNT=<email or phone>"; exit 1; }
	docker compose exec -T auth_service python -m app.cli revoke-admin "$$ACCOUNT"

.PHONY: db-backup
db-backup: ## Back up every service database to backups/
	$(call log,"Backing up databases...")
	@mkdir -p backups
	docker compose exec -T postgres sh -c 'pg_dumpall -U "$$POSTGRES_USER"' \
		| gzip > backups/alakhservice_$(shell date +%Y%m%d_%H%M%S).sql.gz
	$(call success,"Databases backed up to backups/")

# =============================================================================
# BUILD
# =============================================================================

.PHONY: build
build: build-images build-web ## Build all artifacts (Docker images + web bundle)

.PHONY: build-images
build-images: ## Build all Docker images
	$(call log,"Building Docker images...")
	docker compose build --parallel
	$(call success,"Docker images built")

.PHONY: build-image/%
build-image/%: ## Build a specific service image: make build-image/api_gateway
	$(call log,"Building image: $*...")
	docker build \
		--build-arg VERSION=$(VERSION) \
		--build-arg COMMIT=$(COMMIT) \
		--build-arg BUILD_DATE=$(BUILD_DATE) \
		-t $(REGISTRY)/$*:$(DOCKER_TAG) \
		-t $(REGISTRY)/$*:latest \
		-f $(SERVICES_DIR)/$*/Dockerfile \
		$(SERVICES_DIR)/$*
	$(call success,"Image built: $(REGISTRY)/$*:$(DOCKER_TAG)")

.PHONY: build-web
build-web: ## Build web frontend
	$(call log,"Building web frontend...")
	@for app in $(WEB_APPS); do \
		echo "→ $$app"; \
		(cd "$$app" && $(NPM) run build) || exit 1; \
	done
	$(call success,"Web frontend built")

.PHONY: build-mobile-android
build-mobile-android: ## Build Flutter Android APK (release)
	$(call log,"Building Android APK...")
	cd $(MOBILE_DIR) && flutter build apk --release
	$(call success,"Android APK built: $(MOBILE_DIR)/build/app/outputs/flutter-apk/app-release.apk")

.PHONY: build-mobile-ios
build-mobile-ios: ## Build Flutter iOS archive (release)
	$(call log,"Building iOS archive...")
	cd $(MOBILE_DIR) && flutter build ios --release
	$(call success,"iOS archive built")

# =============================================================================
# CLEAN
# =============================================================================

.PHONY: clean
clean: clean-python clean-node clean-docker clean-coverage ## Clean all build artifacts

.PHONY: clean-python
clean-python: ## Remove Python build artifacts and caches
	$(call log,"Cleaning Python artifacts...")
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete
	$(call success,"Python artifacts cleaned")

.PHONY: clean-node
clean-node: ## Remove Node.js build artifacts and caches
	$(call log,"Cleaning Node artifacts...")
	find . -type d -name "node_modules" -not -path "*/.git/*" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "dist" -not -path "*/.git/*" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".next" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".turbo" -exec rm -rf {} + 2>/dev/null || true
	$(call success,"Node artifacts cleaned")

.PHONY: clean-docker
clean-docker: ## Stop and remove all project containers, images, and volumes
	$(call log,"Cleaning Docker resources...")
	docker compose -f docker-compose.yml -f docker-compose.dev.yml down \
		--volumes --remove-orphans --rmi local
	$(call success,"Docker resources cleaned")

.PHONY: clean-coverage
clean-coverage: ## Remove coverage reports
	rm -rf coverage/ htmlcov/
	$(call success,"Coverage reports cleaned")

.PHONY: clean-all
clean-all: clean ## Clean everything including the virtualenv
	rm -rf $(VENV)
	$(call success,"Everything cleaned (including venv)")

# =============================================================================
# UTILITIES
# =============================================================================

.PHONY: version
version: ## Display project version
	@echo "$(PROJECT) $(VERSION) ($(COMMIT)) built on $(BUILD_DATE)"

.PHONY: check-deps
check-deps: ## List outdated dependencies in every project (needs make setup)
	@for req in $(PY_PROJECTS); do \
		dir=$$(dirname "$$req"); \
		echo "→ $$dir"; \
		"$$dir/.venv/bin/pip" list --outdated; \
	done
	@for app in $(NODE_PROJECTS); do \
		echo "→ $$app"; \
		(cd "$$app" && $(NPM) outdated) || true; \
	done

.PHONY: pre-commit-run
pre-commit-run: ## Run all pre-commit hooks against all files
	$(VENV)/bin/pre-commit run --all-files

.PHONY: pre-commit-update
pre-commit-update: ## Update pre-commit hook versions
	$(VENV)/bin/pre-commit autoupdate

.PHONY: redis-cli
redis-cli: ## Open a redis-cli session
	docker compose exec redis redis-cli

.PHONY: health
health: ## Check health of the gateway and every service (needs make dev)
	$(call log,"Checking service health...")
	@for svc_port in api_gateway:3000 auth_service:8001 user_service:8002 shop_service:8003 \
		booking_service:8004 payment_service:8005 notification_service:8006 tracking_service:8007 \
		queue_service:8008 dispatch_service:8009 analytics_service:8010 dispute_service:8011 \
		trust_risk_service:8012 admin_service:8013 compliance_service:8014 pricing_engine:8015 \
		service_catalog_service:8016 catalog_service:8017; do \
		svc=$${svc_port%%:*}; port=$${svc_port##*:}; \
		status=$$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$$port/health 2>/dev/null || true); \
		if [ "$$status" = "200" ]; then \
			printf "  $(GREEN)✓$(RESET) %-30s $(GREEN)healthy$(RESET)\n" $$svc; \
		else \
			printf "  $(RED)✗$(RESET) %-30s $(RED)unhealthy (HTTP $$status)$(RESET)\n" $$svc; \
		fi; \
	done

.PHONY: ps
ps: ## Show running containers and their status
	docker compose ps

.PHONY: stats
stats: ## Show container resource usage
	docker stats --no-stream
