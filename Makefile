.PHONY: help up down restart logs ps seed daily demo test clean env check-env

# Default target
.DEFAULT_GOAL := help

# Load environment variables
ifneq (,$(wildcard .env))
    include .env
    export
endif

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

help: ## Show this help message
	@echo "$(BLUE)CollectOS Makefile$(NC)"
	@echo ""
	@echo "$(GREEN)Available targets:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(BLUE)%-15s$(NC) %s\n", $$1, $$2}'

env: ## Create .env from .env.example if it doesn't exist
	@if [ ! -f .env ]; then \
		echo "$(YELLOW)Creating .env from .env.example...$(NC)"; \
		cp .env.example .env; \
		echo "$(GREEN)✓ Created .env - please review and customize$(NC)"; \
	else \
		echo "$(GREEN).env already exists$(NC)"; \
	fi

check-env: ## Check if .env exists
	@if [ ! -f .env ]; then \
		echo "$(RED)Error: .env not found. Run 'make env' first.$(NC)"; \
		exit 1; \
	fi

up: check-env ## Start all services (postgres + metabase)
	@echo "$(BLUE)Starting CollectOS services...$(NC)"
	docker-compose up -d
	@echo "$(GREEN)✓ Services started$(NC)"
	@echo "$(YELLOW)Postgres:$(NC)  localhost:${POSTGRES_PORT:-5432}"
	@echo "$(YELLOW)Metabase:$(NC) http://localhost:${METABASE_PORT:-3000}"

up-dev: check-env ## Start all services including dev tools (mailpit)
	@echo "$(BLUE)Starting CollectOS services with dev tools...$(NC)"
	docker-compose --profile dev up -d
	@echo "$(GREEN)✓ Services started$(NC)"
	@echo "$(YELLOW)Postgres:$(NC)  localhost:${POSTGRES_PORT:-5432}"
	@echo "$(YELLOW)Metabase:$(NC) http://localhost:${METABASE_PORT:-3000}"
	@echo "$(YELLOW)Mailpit:$(NC)  http://localhost:8025"

down: ## Stop and remove all services
	@echo "$(BLUE)Stopping CollectOS services...$(NC)"
	docker-compose down
	@echo "$(GREEN)✓ Services stopped$(NC)"

down-volumes: ## Stop services and remove volumes (WARNING: deletes all data)
	@echo "$(RED)WARNING: This will delete all data!$(NC)"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker-compose down -v; \
		echo "$(GREEN)✓ Services and volumes removed$(NC)"; \
	else \
		echo "$(YELLOW)Cancelled$(NC)"; \
	fi

restart: down up ## Restart all services

logs: ## Tail logs from all services
	docker-compose logs -f

logs-postgres: ## Tail postgres logs
	docker-compose logs -f postgres

logs-metabase: ## Tail metabase logs
	docker-compose logs -f metabase

ps: ## Show running containers
	docker-compose ps

db-shell: ## Open psql shell to database
	@echo "$(BLUE)Connecting to database...$(NC)"
	docker-compose exec postgres psql -U ${POSTGRES_USER:-collectos} -d ${POSTGRES_DB:-collectos}

db-migrate: check-env ## Run database migrations (idempotent)
	@echo "$(BLUE)Running database migrations...$(NC)"
	@# Migrations run automatically on first container start via docker-entrypoint-initdb.d
	@# For subsequent migrations, we'll use a Python script (to be created in later sessions)
	@echo "$(YELLOW)Note: Initial migrations run automatically on first 'make up'$(NC)"
	@echo "$(YELLOW)For manual migration, run SQL files in infra/migrations/ via psql$(NC)"

seed: check-env ## Generate and load synthetic data
	@echo "$(BLUE)Generating synthetic data...$(NC)"
	@if [ "${SMALL_MODE}" = "1" ]; then \
		echo "$(YELLOW)Running in SMALL_MODE (30k accounts)$(NC)"; \
	else \
		echo "$(YELLOW)Running in FULL_MODE (300k accounts - may take ~30 min)$(NC)"; \
	fi
	python -m synthgen.seed
	@echo "$(GREEN)✓ Seed complete$(NC)"

daily: check-env ## Run the daily pipeline (ingest → transform → score → allocate → queue)
	@echo "$(BLUE)Running daily pipeline...$(NC)"
	@echo "$(YELLOW)Step 1/2: Running dbt transformations...$(NC)"
	cd dbt && dbt run --profiles-dir .
	@echo "$(GREEN)✓ dbt models built$(NC)"
	@echo "$(YELLOW)Step 2/2: Running dbt tests...$(NC)"
	cd dbt && dbt test --profiles-dir .
	@echo "$(GREEN)✓ dbt tests passed$(NC)"
	@echo "$(GREEN)✓ Daily pipeline complete$(NC)"
	@echo "$(YELLOW)Note: Scoring, allocation, and queueing will be added in Sessions 5-7$(NC)"

demo: check-env ## Run full end-to-end demo (complete workflow walkthrough)
	@echo "$(BLUE)Running end-to-end demo...$(NC)"
	python scripts/demo.py
	@echo "$(GREEN)✓ Demo complete$(NC)"

test: ## Run all tests (pytest + dbt tests)
	@echo "$(BLUE)Running tests...$(NC)"
	@# dbt tests
	@echo "$(YELLOW)Running dbt tests...$(NC)"
	cd dbt && dbt test --profiles-dir .
	@# Python tests (to be added later)
	@if command -v pytest >/dev/null 2>&1 && [ -d "quality/" ]; then \
		echo "$(YELLOW)Running pytest...$(NC)"; \
		pytest quality/ -v; \
	else \
		echo "$(YELLOW)pytest tests will be added in later sessions$(NC)"; \
	fi
	@echo "$(GREEN)✓ All tests passed$(NC)"

lint: ## Run linters (black, mypy)
	@echo "$(BLUE)Running linters...$(NC)"
	@if command -v black >/dev/null 2>&1; then \
		echo "$(YELLOW)Running black...$(NC)"; \
		black --check .; \
	else \
		echo "$(YELLOW)black not installed$(NC)"; \
	fi
	@if command -v mypy >/dev/null 2>&1; then \
		echo "$(YELLOW)Running mypy...$(NC)"; \
		mypy --ignore-missing-imports .; \
	else \
		echo "$(YELLOW)mypy not installed$(NC)"; \
	fi

format: ## Format code with black
	@echo "$(BLUE)Formatting code...$(NC)"
	@if command -v black >/dev/null 2>&1; then \
		black .; \
		echo "$(GREEN)✓ Code formatted$(NC)"; \
	else \
		echo "$(RED)black not installed$(NC)"; \
		exit 1; \
	fi

clean: ## Clean temporary files and caches
	@echo "$(BLUE)Cleaning temporary files...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type f -name "*.log" -delete 2>/dev/null || true
	rm -rf dbt/target/ dbt/logs/ .dagster/ dagster_home/ 2>/dev/null || true
	@echo "$(GREEN)✓ Cleaned$(NC)"

status: ps ## Show status (alias for ps)

health: ## Check health of all services
	@echo "$(BLUE)Checking service health...$(NC)"
	@docker-compose ps --format json | python3 -c "import sys, json; \
	data = [json.loads(line) for line in sys.stdin]; \
	healthy = all(s.get('Health') == 'healthy' or s.get('State') == 'running' for s in data); \
	print('$(GREEN)✓ All services healthy$(NC)' if healthy and data else '$(RED)✗ Some services unhealthy$(NC)')"

info: ## Show environment info
	@echo "$(BLUE)CollectOS Environment Info$(NC)"
	@echo ""
	@echo "$(YELLOW)Mode:$(NC) $${SMALL_MODE:-1}" | sed 's/1/SMALL (30k accounts)/; s/0/FULL (300k accounts)/'
	@echo "$(YELLOW)Database:$(NC) postgresql://${POSTGRES_USER:-collectos}@localhost:${POSTGRES_PORT:-5432}/${POSTGRES_DB:-collectos}"
	@echo "$(YELLOW)Metabase:$(NC) http://localhost:${METABASE_PORT:-3000}"
	@echo "$(YELLOW)API:$(NC) http://localhost:${API_PORT:-8000}"
	@echo "$(YELLOW)Dagster:$(NC) http://localhost:${DAGSTER_PORT:-3001}"
	@echo ""
	@echo "$(YELLOW)Docker Status:$(NC)"
	@docker-compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
