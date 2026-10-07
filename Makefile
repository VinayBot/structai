.PHONY: setup dev test lint format migrate check-env up down eval load-test mcp mcp-token promote-admin frontend-install frontend-dev frontend-build frontend-test frontend-lint

setup:
	uv sync
	uv run pre-commit install

dev:
	@trap 'kill 0' EXIT INT TERM; \
	uv run uvicorn app.main:app --reload & \
	(cd frontend && npm run dev) & \
	wait

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy app

format:
	uv run ruff format .
	uv run ruff check --fix .

eval:
	uv run python3 scripts/run_eval.py

load-test:
	uv run python3 scripts/load_test.py

mcp:
	uv run python3 -m app.mcp.server

mcp-token:
	uv run python3 scripts/mcp_issue_token.py

promote-admin:
	uv run python3 scripts/promote_admin.py

migrate:
	uv run alembic upgrade head

check-env:
	uv run python3 scripts/check_env.py

up:
	docker-compose up --build -d

down:
	docker-compose down

frontend-install:
	cd frontend && npm install

frontend-dev:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build

frontend-test:
	cd frontend && npx vitest run

frontend-lint:
	cd frontend && npm run lint
