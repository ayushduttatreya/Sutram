.PHONY: dev dev-down test lint typecheck migrate seed openapi contract help

COMPOSE        = docker compose -f infra/docker-compose.yml
COMPOSE_DEV    = $(COMPOSE) -f infra/docker-compose.dev.yml
COMPOSE_TEST   = docker compose -f infra/docker-compose.test.yml
API_URL        ?= http://localhost:8000

help:
	@echo "Sutram Platform — Developer Commands"
	@echo ""
	@echo "  make dev        Start full stack with hot reload"
	@echo "  make dev-down   Stop all services and remove volumes"
	@echo "  make test       Run full test suite (spins up test DBs)"
	@echo "  make lint       Run ruff linter and format check"
	@echo "  make typecheck  Run mypy type checker"
	@echo "  make migrate    Run Alembic migrations for all services"
	@echo "  make seed       Seed development data"
	@echo "  make openapi    Regenerate OpenAPI specs from running services"
	@echo "  make contract   Run Schemathesis contract tests"

dev:
	$(COMPOSE_DEV) up --build

dev-down:
	$(COMPOSE) down -v

test:
	$(COMPOSE_TEST) up -d
	uv run pytest packages/ -v --tb=short
	$(COMPOSE_TEST) down -v

lint:
	uv run ruff check packages/ services/
	uv run ruff format --check packages/ services/

typecheck:
	uv run mypy packages/core/sutram_core

migrate:
	@for service in workflow-service memory-service observability-service; do \
		echo "→ Migrating $$service..."; \
		(cd services/$$service && uv run alembic upgrade head) || exit 1; \
	done

seed:
	uv run python scripts/seed.py

openapi:
	bash scripts/generate_openapi.sh

contract:
	@echo "Running Schemathesis contract tests..."
	uv run schemathesis run $(API_URL)/openapi.json --checks all
