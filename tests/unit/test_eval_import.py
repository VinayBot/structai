import json
from pathlib import Path

import pytest
from sqlalchemy import select

from app.db import get_session_maker
from app.models.eval_run import EvalRun
from app.services.eval_import import import_existing_reports

NO_CASES = Path("does-not-exist.json")


def _report(provider: str | None, case_id: str = "c1") -> dict:
    return {
        "started_at": "2026-01-01T00:00:00+00:00",
        "finished_at": "2026-01-01T00:00:01+00:00",
        "concurrency": 1,
        "total": 1,
        "passed": 1,
        "failed": 0,
        "pass_rate": 1.0,
        "avg_latency_ms": 10.0,
        "p95_latency_ms": 10.0,
        "avg_attempts": 1.0,
        "by_category": {"facts": {"total": 1, "passed": 1}},
        "results": [
            {
                "case_id": case_id,
                "category": "facts",
                "passed": True,
                "reason": None,
                "provider": provider,
                "model": "fake-model",
                "attempts": 1,
                "latency_ms": 10.0,
                "data": {"answer": "Paris"},
                "trace_id": "abc123",
            }
        ],
    }


@pytest.fixture
def reports_dir(tmp_path: Path) -> Path:
    d = tmp_path / "reports"
    d.mkdir()
    (d / "20260101T000000Z.json").write_text(json.dumps(_report("ollama")))
    (d / "compare-20260101T000100Z.json").write_text(
        json.dumps({"ollama": _report("ollama"), "groq": _report("groq")})
    )
    return d


@pytest.mark.asyncio
async def test_import_existing_reports_creates_expected_rows(app, reports_dir):
    imported = await import_existing_reports(
        get_session_maker(), reports_dir=reports_dir, cases_path=NO_CASES
    )

    assert imported == 3

    async with get_session_maker()() as session:
        rows = (await session.scalars(select(EvalRun))).all()

    assert len(rows) == 3
    assert sorted(r.provider for r in rows) == ["groq", "ollama", "ollama"]
    assert all(r.source == "imported" for r in rows)
    import_keys = {r.import_key for r in rows}
    assert import_keys == {
        "20260101T000000Z.json",
        "compare-20260101T000100Z.json:ollama",
        "compare-20260101T000100Z.json:groq",
    }


@pytest.mark.asyncio
async def test_import_existing_reports_is_idempotent(app, reports_dir):
    first = await import_existing_reports(
        get_session_maker(), reports_dir=reports_dir, cases_path=NO_CASES
    )
    second = await import_existing_reports(
        get_session_maker(), reports_dir=reports_dir, cases_path=NO_CASES
    )

    assert first == 3
    assert second == 0

    async with get_session_maker()() as session:
        rows = (await session.scalars(select(EvalRun))).all()
    assert len(rows) == 3


@pytest.mark.asyncio
async def test_import_existing_reports_missing_dir_returns_zero(app, tmp_path):
    imported = await import_existing_reports(
        get_session_maker(), reports_dir=tmp_path / "does-not-exist", cases_path=NO_CASES
    )
    assert imported == 0


@pytest.mark.asyncio
async def test_import_plain_report_infers_dominant_provider_when_mixed(app, tmp_path):
    d = tmp_path / "reports"
    d.mkdir()
    report = _report("ollama")
    report["results"].append({**report["results"][0], "case_id": "c2", "provider": "ollama"})
    report["results"].append({**report["results"][0], "case_id": "c3", "provider": None})
    report["total"] = 3
    (d / "mixed.json").write_text(json.dumps(report))

    await import_existing_reports(get_session_maker(), reports_dir=d, cases_path=NO_CASES)

    async with get_session_maker()() as session:
        row = (await session.scalars(select(EvalRun))).one()
    assert row.provider == "ollama"
