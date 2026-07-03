.DEFAULT_GOAL := help

PYTHON ?= python
NPM ?= npm
DOCKER ?= docker
COMPOSE ?= docker compose

.PHONY: help install dev test lint migrate seed build clean

help:
	@echo "Available targets:"
	@echo "  install  Install backend, frontend, and quality-tool dependencies"
	@echo "  dev      Apply migrations and start the development stack"
	@echo "  test     Run all backend and frontend tests"
	@echo "  lint     Run all pre-commit quality checks"
	@echo "  migrate  Start PostgreSQL and apply Alembic migrations"
	@echo "  seed     Import skill and major seed data"
	@echo "  build    Build production backend and frontend images"
	@echo "  clean    Remove explicit local coverage artifacts"

install:
	$(PYTHON) -m pip install -r backend/requirements.txt
	$(PYTHON) -m pip install pre-commit
	$(NPM) --prefix frontend ci
	$(PYTHON) -m pre_commit install --hook-type pre-commit --hook-type pre-push

migrate:
	$(COMPOSE) up -d db
	$(COMPOSE) build backend
	$(COMPOSE) run --rm backend sh -c "cd /app/backend && alembic upgrade head"

dev: migrate
	$(COMPOSE) up --build

test:
	$(PYTHON) -m pytest backend/tests tests -q
	$(NPM) --prefix frontend test
	$(NPM) --prefix frontend run typecheck

lint:
	$(PYTHON) -m pre_commit run --all-files

seed: migrate
	$(COMPOSE) run --rm backend python -m backend.scripts.seed_skills
	$(COMPOSE) run --rm backend python -m backend.scripts.seed_majors

build:
	$(DOCKER) build --target prod -f backend/Dockerfile -t match-backend:prod .
	$(DOCKER) build --target prod -f frontend/Dockerfile -t match-frontend:prod frontend

clean:
	$(PYTHON) -c "from pathlib import Path; Path('.coverage').unlink(missing_ok=True)"
	$(PYTHON) -c "from pathlib import Path; Path('coverage.xml').unlink(missing_ok=True)"
	@echo "Directory caches are retained; remove them manually when needed."
