# Contributing

## Setup

```bash
uv sync
uv run pre-commit install
cp .env.example .env
uv run alembic upgrade head
cd frontend && npm install
```

## Branches and commits

Work happens on a branch off `main`, named `<type>/<short-description>` (e.g. `feat/admin-usage-dashboard`, `fix/rate-limit-off-by-one`). Open a PR against `main` rather than committing directly to it.

Commit messages use a `<type>(<scope>): <summary>` subject line, `<scope>` being whatever's most specific (a module, a feature area) — look at `git log` for examples. Common types:

| Type | For |
|---|---|
| `feat` | A new capability |
| `fix` | A bug fix |
| `docs` | Documentation only |
| `test` | Tests only, no behavior change |
| `ci` | CI/CD, pre-commit, Docker, packaging |
| `chore` | Everything else (deps, cleanup) |

Keep commits focused — one logical change each, passing lint/type-check/tests before the next one starts. A PR with five commits that each build and pass is easier to review (and bisect) than one with the same diff squashed into a single commit.

## Before opening a PR

```bash
make lint   # ruff check, ruff format --check, mypy
make test   # pytest, 85% coverage gate
cd frontend && npm run lint && npm run build && npx vitest run
```

`pre-commit` runs the fast parts of this automatically on `git commit` once installed (see Setup). The Playwright suite in `frontend/e2e/` needs a live backend + frontend + reachable Ollama (`make dev` in one terminal, `npx playwright test` in another) — it isn't part of pre-commit or CI, so run it by hand for anything touching auth, the structured-answer path, or the Architecture tab's live-run replay.

If you touch a route's path, method, or add/remove one entirely, also check:
- `app/services/arch_endpoints.py` — `tests/unit/test_arch_endpoint_coverage.py` enforces that every real route is claimed by exactly one Architecture-tab node.
- `frontend/src/lib/api.ts` and `frontend/vite.config.ts`'s dev-proxy map — `frontend/src/lib/apiProxy.test.ts` enforces that every path prefix used there is proxied.
- `docs/API.md`.

## Database changes

Generate migrations with `uv run alembic revision --autogenerate -m "..."`, then open the generated file: SQLite needs `op.batch_alter_table(...)` for anything beyond a plain `ADD COLUMN` (dropping/altering a column, adding a constraint) — autogenerate doesn't wrap these in batch mode by default, but every migration in `alembic/versions/` does, so match that. Verify both directions against your local dev DB before committing:

```bash
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
```
