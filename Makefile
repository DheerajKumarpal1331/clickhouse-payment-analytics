# ============================================================
# Payment Platform — developer command surface.
#   make up        bring up infra + monitoring + dev tools
#   make down      stop and remove containers
#   make restart   down + up
#   make logs      tail all logs (S=postgres for one service)
#   make test      run platform tests
#   make lint      lint SQL + Python
#   make seed-data generate synthetic data and load it
# Profiles:  make up PROFILE=pipeline   (or apps / ml / airflow)
# Env:       make up ENV=qa             (uses .env.qa)
# ============================================================
ENV ?= dev
PROFILE ?=
S ?=
COMPOSE := docker compose
PROFILE_FLAG := $(if $(PROFILE),--profile $(PROFILE),)

.DEFAULT_GOAL := help
.PHONY: help env up up-all down restart logs ps health test lint seed-data \
        init-clickhouse psql ch clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

env: ## Materialize .env from .env.$(ENV)
	cp .env.$(ENV) .env
	@echo "using .env.$(ENV)"

up: env ## Start the platform (infra+monitoring+devtools; add PROFILE=...)
	$(COMPOSE) $(PROFILE_FLAG) up -d
	@echo "Kafka UI :8080  Grafana :3000  MLflow :5000  pgAdmin :5050  CH-UI :5521  Jupyter :8888"

up-all: env ## Start everything (all profiles)
	$(COMPOSE) --profile pipeline --profile apps --profile ml --profile airflow up -d

down: ## Stop and remove containers (keeps volumes)
	$(COMPOSE) --profile pipeline --profile apps --profile ml --profile airflow down

restart: down up ## Restart the platform

logs: ## Tail logs (S=<service> for one)
	$(COMPOSE) logs -f --tail=100 $(S)

ps: ## List running services
	$(COMPOSE) ps

health: ## Show health status of all containers
	@docker ps --filter "name=payments-" --format "table {{.Names}}\t{{.Status}}"

test: ## Run platform tests (Postgres OLTP suite + data-generator smoke)
	bash scripts/run_tests.sh

lint: ## Lint Python (ruff if present) and check SQL parses
	@command -v ruff >/dev/null 2>&1 && ruff check data_generator kafka || echo "ruff not installed; skipping py lint"
	@echo "SQL lint: rely on apply.sh dry-run in CI"

seed-data: ## Generate synthetic data and load into Postgres + ClickHouse
	bash scripts/seed_data.sh

init-clickhouse: ## (Re)apply ClickHouse DDL into the running container
	bash docker/clickhouse/apply.sh

psql: ## Open a psql shell on the payments DB
	$(COMPOSE) exec postgres psql -U $${POSTGRES_USER:-payments} -d $${POSTGRES_DB:-payments}

ch: ## Open a clickhouse-client shell
	$(COMPOSE) exec clickhouse clickhouse-client

clean: ## Stop and DELETE volumes (full reset)
	$(COMPOSE) --profile pipeline --profile apps --profile ml --profile airflow down -v
