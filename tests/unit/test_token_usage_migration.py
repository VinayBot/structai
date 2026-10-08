"""Exercises alembic/versions/6a5f90d6a7bb_*.py (the token-usage columns migration)
upgrade/downgrade against a real, throwaway sqlite file - not just that the models
look right, but that the migration itself actually applies and reverts cleanly."""

import asyncio
import os
import sqlite3
from pathlib import Path

import pytest
from alembic.config import Config

from alembic import command
from app.config import get_settings
from app.db import reset_db_caches

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _alembic_config(db_path: Path) -> Config:
    cfg = Config(str(_REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(_REPO_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db_path}")
    return cfg


def _columns(db_path: Path, table: str) -> set[str]:
    conn = sqlite3.connect(db_path)
    try:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    finally:
        conn.close()


async def _run_migration(db_path: Path, direction: str, target: str) -> None:
    """alembic/env.py drives an async engine via asyncio.run() internally, which
    can't nest inside pytest-asyncio's already-running loop - run it in a worker
    thread (its own fresh loop) instead. env.py also reads DATABASE_URL through
    app.config.get_settings()/app.db.get_engine(), same lru_cache singletons the
    rest of the app uses, so point those at this throwaway db first."""
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
    get_settings.cache_clear()
    reset_db_caches()

    cfg = _alembic_config(db_path)

    def _invoke() -> None:
        if direction == "upgrade":
            command.upgrade(cfg, target)
        else:
            command.downgrade(cfg, target)

    await asyncio.to_thread(_invoke)
    get_settings.cache_clear()
    reset_db_caches()


@pytest.mark.asyncio
async def test_upgrade_adds_token_usage_columns(tmp_path):
    db_path = tmp_path / "migration_test.db"
    await _run_migration(db_path, "upgrade", "head")

    assert {"prompt_tokens", "completion_tokens"} <= _columns(db_path, "messages")
    assert {"prompt_tokens", "completion_tokens"} <= _columns(db_path, "eval_case_results")


@pytest.mark.asyncio
async def test_downgrade_removes_only_the_new_columns(tmp_path):
    db_path = tmp_path / "migration_test.db"
    await _run_migration(db_path, "upgrade", "head")
    await _run_migration(db_path, "downgrade", "-1")

    messages_cols = _columns(db_path, "messages")
    eval_cols = _columns(db_path, "eval_case_results")
    assert "prompt_tokens" not in messages_cols
    assert "completion_tokens" not in messages_cols
    assert "prompt_tokens" not in eval_cols
    assert "completion_tokens" not in eval_cols
    # The downgrade removed exactly the new columns, not the whole table.
    assert {"id", "chat_id", "content"} <= messages_cols
    assert {"id", "eval_run_id", "case_id"} <= eval_cols


@pytest.mark.asyncio
async def test_upgrade_downgrade_upgrade_roundtrip(tmp_path):
    db_path = tmp_path / "migration_test.db"
    await _run_migration(db_path, "upgrade", "head")
    await _run_migration(db_path, "downgrade", "-1")
    await _run_migration(db_path, "upgrade", "head")

    assert {"prompt_tokens", "completion_tokens"} <= _columns(db_path, "messages")
    assert {"prompt_tokens", "completion_tokens"} <= _columns(db_path, "eval_case_results")
