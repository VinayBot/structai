.PHONY: setup dev test lint migrate check-env up down eval load-test mcp mcp-token promote-admin frontend-install frontend-dev frontend-build frontend-test frontend-lint

setup:
	python3 -m venv .venv
	.venv/bin/pip install -e ".[dev]"

dev:
	@trap 'kill 0' EXIT INT TERM; \
	uvicorn app.main:app --reload & \
	(cd frontend && npm run dev) & \
	wait

test:
	pytest

lint:
	ruff check .
	mypy app

eval:
	python3 scripts/run_eval.py

load-test:
	python3 scripts/load_test.py

mcp:
	python3 -m app.mcp.server

mcp-token:
	python3 scripts/mcp_issue_token.py

promote-admin:
	python3 scripts/promote_admin.py

migrate:
	alembic upgrade head

check-env:
	python3 scripts/check_env.py

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
