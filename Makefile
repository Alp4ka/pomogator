.PHONY: install lock lint format test check migrate dev bot sync up down

install:
	uv sync --frozen
	cd frontend && npm ci

lock:
	uv lock

lint:
	uv run ruff check backend tests
	uv run ruff format --check backend tests
	uv run mypy backend/src
	cd frontend && npm run lint && npm run typecheck

format:
	uv run ruff check --fix backend tests
	uv run ruff format backend tests

test:
	uv run pytest
	cd frontend && npm test -- --run

check: lint test

migrate:
	uv run alembic upgrade head

dev:
	uv run uvicorn pomogator.main:app --app-dir backend/src --reload

bot:
	uv run pomogator-bot

sync:
	PYTHONPATH=backend/src uv run celery -A pomogator.worker.celery call pomogator.sync_all

up:
	docker compose up --build -d

down:
	docker compose down
