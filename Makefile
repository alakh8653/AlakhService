# =============================================================================
# AlakhService – Makefile
# =============================================================================
# Usage: make <target>
# Run `make help` to list all available targets.
# =============================================================================

SHELL := /bin/bash
.ONESHELL:
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
MOBILE_DIR   := $(ROOT_DIR)/mobile
WEB_DIR      := $(ROOT_DIR)/web
INFRA_DIR    := $(ROOT_DIR)/infra
DOCS_DIR     := $(ROOT_DIR)/docs
SCRIPTS_DIR  := $(ROOT_DIR)/scripts

# ── Python settings ───────────────────────────────────────────────────────────
PYTHON       := python3.11
VENV         := .venv
PIP          := $(VENV)/bin/pip
PYTHON_VENV  := $(VENV)/bin/python

# ── Node settings ─────────────────────────────────────────────────────────────
NODE         := node
NPM          := npm
PNPM         := pnpm

# ── Colors ────────────────────────────────────────────────────────────────────
RESET  := \033[0m
BOLD   := \033[1m
GREEN  := \033[32m
YELLOW := \033[33m
CYAN   := \033[36m
RED    := \033[31m

# ── Helpers ───────────────────────────────────────────────────────────────────
define log
	@printf "$(BOLD)$(CYAN)[$(PROJECT)]$(RESET) $(1)\n"
endef

define success
	@printf "$(BOLD)$(GREEN)✓ $(1)$(RESET)\n"
endef

define warn
	@printf "$(BOLD)$(YELLOW)⚠ $(1)$(RESET)\n"
endef

define error
	@printf "$(BOLD)$(RED)✗ $(1)$(RESET)\n"
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
	@for svc_req in $(SERVICES_DIR)/*/requirements.txt; do \
		$(PIP) install -r "$$svc_req" 2>/dev/null || true; \
	done
	$(call success,"Python environment ready")

.PHONY: setup-node
setup-node: ## Install Node.js dependencies
	$(call log,"Installing Node.js dependencies...")
	@if [ -f pnpm-lock.yaml ]; then \
		$(PNPM) install --frozen-lockfile; \
	elif [ -f package-lock.json ]; then \
		$(NPM) ci; \
	elif [ -f package.json ]; then \
		$(NPM) install; \
	else \
		echo "No package.json found, skipping Node install."; \
	fi
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

.PHONY: setup-infra
setup-infra: ## Initialise Terraform
	$(call log,"Initialising Terraform...")
	cd $(INFRA_DIR)/terraform && terraform init -upgrade
	$(call success,"Terraform initialised")

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
	docker compose -f docker-compose.yml -f docker-compose.dev.yml \
		up postgres redis kafka zookeeper elasticsearch \
		api-gateway auth-service user-service shop-service \
		booking-service payment-service notification-service tracking-service

.PHONY: dev-infra
dev-infra: ## Start only infrastructure services (postgres, redis, kafka, es)
	$(call log,"Starting infrastructure services...")
	docker compose up -d postgres redis kafka zookeeper elasticsearch minio

.PHONY: dev-web
dev-web: ## Start web frontend in dev mode
	$(call log,"Starting web dev server...")
	cd $(WEB_DIR) && $(PNPM) dev

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
logs/%: ## Follow logs for a specific service: make logs/auth-service
	docker compose logs -f --tail=200 $*

.PHONY: shell/%
shell/%: ## Open a shell in a running service: make shell/api-gateway
	docker compose exec $* /bin/sh

# =============================================================================
# TESTING
# =============================================================================

.PHONY: test
test: test-python test-node ## Run all tests

.PHONY: test-python
test-python: ## Run all Python tests with coverage
	$(call log,"Running Python tests...")
	$(PYTHON_VENV) -m pytest \
		--cov=services \
		--cov-report=term-missing \
		--cov-report=html:coverage/python \
		--cov-report=xml:coverage/python/coverage.xml \
		--cov-fail-under=80 \
		-v \
		$(SERVICES_DIR)
	$(call success,"Python tests passed")

.PHONY: test-node
test-node: ## Run all Node/TypeScript tests with coverage
	$(call log,"Running TypeScript tests...")
	@if [ -f package.json ]; then \
		$(PNPM) run test --coverage; \
	fi
	$(call success,"TypeScript tests passed")

.PHONY: test-mobile
test-mobile: ## Run Flutter widget and unit tests
	$(call log,"Running Flutter tests...")
	cd $(MOBILE_DIR) && flutter test --coverage
	$(call success,"Flutter tests passed")

.PHONY: test-e2e
test-e2e: ## Run end-to-end tests (requires running services)
	$(call log,"Running E2E tests...")
	$(PNPM) run test:e2e
	$(call success,"E2E tests passed")

.PHONY: test-integration
test-integration: ## Run integration tests
	$(call log,"Running integration tests...")
	$(PYTHON_VENV) -m pytest \
		-m integration \
		-v \
		$(SERVICES_DIR)
	$(call success,"Integration tests passed")

.PHONY: test-load
test-load: ## Run load/performance tests with Locust
	$(call log,"Running load tests...")
	$(PYTHON_VENV) -m locust \
		--headless \
		--users 100 \
		--spawn-rate 10 \
		--run-time 60s \
		-f $(SERVICES_DIR)/load_tests/locustfile.py
	$(call success,"Load tests complete")

.PHONY: test-security
test-security: ## Run security scans (bandit + npm audit + trivy)
	$(call log,"Running security scans...")
	$(PYTHON_VENV) -m bandit -r $(SERVICES_DIR) -ll
	@if [ -f package.json ]; then $(PNPM) audit --audit-level=high; fi
	@which trivy >/dev/null 2>&1 && \
		trivy image $(REGISTRY)/api-gateway:$(DOCKER_TAG) || \
		$(call warn,"trivy not installed, skipping container scan")
	$(call success,"Security scan complete")

.PHONY: coverage
coverage: ## Open HTML coverage report in browser
	@if [ -f coverage/python/index.html ]; then \
		open coverage/python/index.html 2>/dev/null || xdg-open coverage/python/index.html; \
	else \
		$(call error,"No coverage report found. Run 'make test' first."); \
	fi

# =============================================================================
# LINTING & FORMATTING
# =============================================================================

.PHONY: lint
lint: lint-python lint-node lint-yaml lint-docker ## Run all linters

.PHONY: lint-python
lint-python: ## Lint Python code with Ruff + MyPy
	$(call log,"Linting Python...")
	$(PYTHON_VENV) -m ruff check $(SERVICES_DIR)
	$(PYTHON_VENV) -m mypy $(SERVICES_DIR) --ignore-missing-imports
	$(call success,"Python lint passed")

.PHONY: lint-node
lint-node: ## Lint TypeScript/JavaScript with ESLint
	$(call log,"Linting TypeScript...")
	@if [ -f package.json ]; then $(PNPM) run lint; fi
	$(call success,"TypeScript lint passed")

.PHONY: lint-yaml
lint-yaml: ## Lint YAML files with yamllint
	$(call log,"Linting YAML...")
	$(PYTHON_VENV) -m yamllint .
	$(call success,"YAML lint passed")

.PHONY: lint-docker
lint-docker: ## Lint Dockerfiles with hadolint
	$(call log,"Linting Dockerfiles...")
	@find . -name "Dockerfile*" -not -path "*/node_modules/*" \
		| xargs -I{} hadolint {}
	$(call success,"Dockerfile lint passed")

.PHONY: lint-terraform
lint-terraform: ## Lint Terraform with tflint
	$(call log,"Linting Terraform...")
	cd $(INFRA_DIR)/terraform && tflint --recursive
	$(call success,"Terraform lint passed")

.PHONY: format
format: format-python format-node ## Auto-format all code

.PHONY: format-python
format-python: ## Format Python code with Black + Ruff
	$(call log,"Formatting Python...")
	$(PYTHON_VENV) -m black $(SERVICES_DIR)
	$(PYTHON_VENV) -m ruff check --fix $(SERVICES_DIR)
	$(call success,"Python formatted")

.PHONY: format-node
format-node: ## Format TypeScript/JavaScript/CSS with Prettier
	$(call log,"Formatting TypeScript...")
	@if [ -f package.json ]; then $(PNPM) run format; fi
	$(call success,"TypeScript/CSS formatted")

.PHONY: format-mobile
format-mobile: ## Format Dart code
	$(call log,"Formatting Dart...")
	cd $(MOBILE_DIR) && dart format .
	$(call success,"Dart formatted")

.PHONY: format-terraform
format-terraform: ## Format Terraform files
	$(call log,"Formatting Terraform...")
	cd $(INFRA_DIR)/terraform && terraform fmt -recursive
	$(call success,"Terraform formatted")

# =============================================================================
# DATABASE
# =============================================================================

.PHONY: db-migrate
db-migrate: ## Apply all pending database migrations
	$(call log,"Applying database migrations...")
	$(PYTHON_VENV) -m alembic upgrade head
	$(call success,"Migrations applied")

.PHONY: db-migrate/%
db-migrate/%: ## Apply migrations for a specific service: make db-migrate/auth-service
	$(call log,"Applying migrations for $*...")
	cd $(SERVICES_DIR)/$* && $(PYTHON_VENV) -m alembic upgrade head
	$(call success,"Migrations applied for $*")

.PHONY: db-rollback
db-rollback: ## Roll back the last migration
	$(call log,"Rolling back last migration...")
	$(PYTHON_VENV) -m alembic downgrade -1
	$(call warn,"Rolled back 1 migration")

.PHONY: db-new-migration
db-new-migration: ## Create a new migration: make db-new-migration NAME="add_users_table"
	@test -n "$(NAME)" || ($(call error,"NAME is required: make db-new-migration NAME=...") && exit 1)
	$(call log,"Creating migration: $(NAME)...")
	$(PYTHON_VENV) -m alembic revision --autogenerate -m "$(NAME)"
	$(call success,"Migration created")

.PHONY: db-seed
db-seed: ## Seed database with development data
	$(call log,"Seeding database...")
	$(PYTHON_VENV) $(SCRIPTS_DIR)/seed_database.py
	$(call success,"Database seeded")

.PHONY: db-reset
db-reset: ## Drop and recreate database (DESTRUCTIVE)
	$(call warn,"This will DESTROY all data. Press Ctrl-C to cancel...")
	@sleep 3
	$(call log,"Resetting database...")
	docker compose exec postgres psql -U alakh -c "DROP DATABASE IF EXISTS alakhservice;"
	docker compose exec postgres psql -U alakh -c "CREATE DATABASE alakhservice;"
	$(MAKE) db-migrate
	$(MAKE) db-seed
	$(call success,"Database reset complete")

.PHONY: db-shell
db-shell: ## Open a psql shell
	docker compose exec postgres psql -U alakh alakhservice

.PHONY: db-backup
db-backup: ## Backup the database to backups/
	$(call log,"Backing up database...")
	@mkdir -p backups
	docker compose exec -T postgres pg_dump -U alakh alakhservice \
		| gzip > backups/alakhservice_$(shell date +%Y%m%d_%H%M%S).sql.gz
	$(call success,"Database backed up to backups/")

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
build-image/%: ## Build a specific service image: make build-image/api-gateway
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
	@if [ -d $(WEB_DIR) ] && [ -f $(WEB_DIR)/package.json ]; then \
		cd $(WEB_DIR) && $(PNPM) run build; \
	fi
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
# PUBLISH / DEPLOY
# =============================================================================

.PHONY: publish
publish: ## Push all Docker images to registry
	$(call log,"Publishing images to $(REGISTRY)...")
	@for service in api-gateway auth-service user-service shop-service \
		booking-service payment-service notification-service tracking-service; do \
		docker push $(REGISTRY)/$$service:$(DOCKER_TAG); \
		docker push $(REGISTRY)/$$service:latest; \
	done
	$(call success,"Images published")

.PHONY: deploy-staging
deploy-staging: ## Deploy to staging environment
	$(call log,"Deploying to staging...")
	./$(SCRIPTS_DIR)/deploy.sh staging $(VERSION)
	$(call success,"Deployed to staging")

.PHONY: deploy-production
deploy-production: ## Deploy to production (requires confirmation)
	$(call warn,"Deploying to PRODUCTION. Are you sure? [y/N]")
	@read answer; \
	if [ "$$answer" = "y" ] || [ "$$answer" = "Y" ]; then \
		./$(SCRIPTS_DIR)/deploy.sh production $(VERSION); \
	else \
		echo "Deployment cancelled."; \
	fi

.PHONY: deploy-k8s
deploy-k8s: ## Apply Kubernetes manifests
	$(call log,"Applying Kubernetes manifests...")
	kubectl apply -f $(INFRA_DIR)/kubernetes/ --recursive
	$(call success,"Kubernetes manifests applied")

.PHONY: rollout-status
rollout-status: ## Check Kubernetes rollout status
	@for deploy in api-gateway auth-service user-service shop-service \
		booking-service payment-service notification-service tracking-service; do \
		kubectl rollout status deployment/$$deploy -n alakhservice; \
	done

.PHONY: helm-install
helm-install: ## Install Helm chart
	$(call log,"Installing Helm chart...")
	helm upgrade --install alakhservice $(INFRA_DIR)/helm/alakhservice \
		--namespace alakhservice \
		--create-namespace \
		--values $(INFRA_DIR)/helm/alakhservice/values.yaml \
		--set image.tag=$(DOCKER_TAG)
	$(call success,"Helm chart installed")

# =============================================================================
# INFRASTRUCTURE (Terraform)
# =============================================================================

.PHONY: tf-plan
tf-plan: ## Terraform plan
	$(call log,"Running terraform plan...")
	cd $(INFRA_DIR)/terraform && terraform plan -out=tfplan

.PHONY: tf-apply
tf-apply: ## Terraform apply
	$(call log,"Running terraform apply...")
	cd $(INFRA_DIR)/terraform && terraform apply tfplan

.PHONY: tf-destroy
tf-destroy: ## Terraform destroy (DESTRUCTIVE)
	$(call warn,"This will DESTROY cloud infrastructure! Ctrl-C to cancel...")
	@sleep 5
	cd $(INFRA_DIR)/terraform && terraform destroy

.PHONY: tf-output
tf-output: ## Show Terraform outputs
	cd $(INFRA_DIR)/terraform && terraform output

# =============================================================================
# CODE GENERATION
# =============================================================================

.PHONY: generate
generate: generate-proto generate-openapi ## Run all code generators

.PHONY: generate-proto
generate-proto: ## Generate gRPC / Protobuf code
	$(call log,"Generating Protobuf code...")
	@find $(SERVICES_DIR) -name "*.proto" | while read proto; do \
		python -m grpc_tools.protoc \
			-I$(SERVICES_DIR)/proto \
			--python_out=$(SERVICES_DIR) \
			--pyi_out=$(SERVICES_DIR) \
			--grpc_python_out=$(SERVICES_DIR) \
			"$$proto"; \
	done
	$(call success,"Protobuf code generated")

.PHONY: generate-openapi
generate-openapi: ## Generate OpenAPI client code
	$(call log,"Generating OpenAPI clients...")
	@if [ -f openapi.yaml ]; then \
		npx @openapitools/openapi-generator-cli generate \
			-i openapi.yaml \
			-g typescript-axios \
			-o $(WEB_DIR)/src/api/generated; \
	fi
	$(call success,"OpenAPI clients generated")

.PHONY: generate-types
generate-types: ## Generate TypeScript types from Python Pydantic models
	$(call log,"Generating TypeScript types...")
	$(PYTHON_VENV) $(SCRIPTS_DIR)/generate_types.py
	$(call success,"TypeScript types generated")

# =============================================================================
# DOCUMENTATION
# =============================================================================

.PHONY: docs
docs: ## Generate and serve documentation
	$(call log,"Building documentation...")
	$(PYTHON_VENV) -m mkdocs build
	$(call success,"Documentation built in site/")

.PHONY: docs-serve
docs-serve: ## Serve documentation locally
	$(PYTHON_VENV) -m mkdocs serve --dev-addr=0.0.0.0:8080

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
check-deps: ## Check for outdated dependencies
	$(call log,"Checking Python dependencies...")
	$(PIP) list --outdated
	$(call log,"Checking Node dependencies...")
	@if [ -f package.json ]; then $(PNPM) outdated; fi

.PHONY: update-deps
update-deps: ## Update dependencies to latest compatible versions
	$(call log,"Updating Python dependencies...")
	$(PIP) install --upgrade pip
	$(PIP) list --outdated --format=freeze | grep -v '^\-e' | cut -d = -f 1 \
		| xargs -n1 $(PIP) install -U 2>/dev/null || true
	$(call log,"Updating Node dependencies...")
	@if [ -f package.json ]; then $(PNPM) update; fi
	$(call success,"Dependencies updated")

.PHONY: pre-commit-run
pre-commit-run: ## Run all pre-commit hooks against all files
	$(VENV)/bin/pre-commit run --all-files

.PHONY: pre-commit-update
pre-commit-update: ## Update pre-commit hook versions
	$(VENV)/bin/pre-commit autoupdate

.PHONY: redis-cli
redis-cli: ## Open a redis-cli session
	docker compose exec redis redis-cli -a $${REDIS_PASSWORD:-""}

.PHONY: kafka-topics
kafka-topics: ## List Kafka topics
	docker compose exec kafka kafka-topics.sh \
		--bootstrap-server localhost:9092 --list

.PHONY: kafka-consume/%
kafka-consume/%: ## Tail a Kafka topic: make kafka-consume/user.events
	docker compose exec kafka kafka-console-consumer.sh \
		--bootstrap-server localhost:9092 \
		--topic $* \
		--from-beginning

.PHONY: health
health: ## Check health of all running services
	$(call log,"Checking service health...")
	@for svc_port in "api-gateway:8000" "auth-service:8001" "user-service:8002" \
		"shop-service:8003" "booking-service:8004" "payment-service:8005" \
		"notification-service:8006" "tracking-service:8007"; do \
		svc=$${svc_port%%:*}; port=$${svc_port##*:}; \
		status=$$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$$port/health 2>/dev/null); \
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
