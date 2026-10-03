import asyncio
import json
import statistics
from collections import Counter
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.core.errors import NotFoundError
from app.gateway.factory import build_gateway, build_single_provider_gateway
from app.gateway.router import ModelGateway
from app.models.eval_run import EvalCaseResult, EvalRun
from app.schemas.eval import (
    EvalCaseResultOut,
    EvalDashboardResponse,
    EvalDeltas,
    EvalLeaderboardEntry,
    EvalRunDetail,
    EvalRunSummary,
)
from eval.runner import load_cases, run_case_traced, summarize_results
from eval.schemas import CaseResult, CategorySummary, EvalReport, GoldenCase

CASES_PATH = Path("eval/cases/golden.json")


def load_available_cases() -> list[GoldenCase]:
    return load_cases(CASES_PATH)


def select_cases(case_ids: list[str] | None) -> list[GoldenCase]:
    cases = load_available_cases()
    if case_ids is None:
        return cases

    by_id = {case.id: case for case in cases}
    missing = [case_id for case_id in case_ids if case_id not in by_id]
    if missing:
        raise NotFoundError(f"unknown case id(s): {', '.join(missing)}")
    return [by_id[case_id] for case_id in case_ids]


def build_gateway_for(
    provider: Literal["gateway", "ollama", "groq"], settings: Settings
) -> ModelGateway:
    if provider == "gateway":
        return build_gateway(settings)
    return build_single_provider_gateway(provider, settings)


@dataclass
class EvalStreamEvent:
    stage: Literal["case_done", "done"]
    case_result: CaseResult | None = None
    report: EvalReport | None = None


async def stream_cases(
    cases: list[GoldenCase],
    gateway: ModelGateway,
    *,
    concurrency: int,
    timeout: float = 30.0,
    max_attempts: int = 3,
) -> AsyncIterator[EvalStreamEvent]:
    started_at = datetime.now(UTC)
    semaphore = asyncio.Semaphore(concurrency)
    tasks = [
        asyncio.create_task(
            run_case_traced(
                gateway, case, semaphore=semaphore, timeout=timeout, max_attempts=max_attempts
            )
        )
        for case in cases
    ]

    results: list[CaseResult] = []
    for task in asyncio.as_completed(tasks):
        result = await task
        results.append(result)
        yield EvalStreamEvent(stage="case_done", case_result=result)

    finished_at = datetime.now(UTC)
    report = summarize_results(
        results, concurrency=concurrency, started_at=started_at, finished_at=finished_at
    )
    yield EvalStreamEvent(stage="done", report=report)


def _dominant_tier(results: list[CaseResult], cases_by_id: dict[str, GoldenCase]) -> str:
    tiers = [cases_by_id[r.case_id].tier for r in results if r.case_id in cases_by_id]
    if not tiers:
        return "fast"
    return Counter(tiers).most_common(1)[0][0]


async def persist_run(
    session: AsyncSession,
    report: EvalReport,
    *,
    provider: str,
    cases: list[GoldenCase],
    source: Literal["api", "imported"] = "api",
    import_key: str | None = None,
) -> str:
    """Write a completed eval run + its per-case results to the DB.

    `cases` supplies the prompt/schema_def to denormalize onto each case-result row
    (captured once, at write time, so historical runs stay self-contained even if
    golden.json cases are later edited or removed).
    """
    cases_by_id = {c.id: c for c in cases}
    model = next((r.model for r in report.results if r.model), None)

    run = EvalRun(
        provider=provider,
        model=model,
        tier=_dominant_tier(report.results, cases_by_id),
        source=source,
        import_key=import_key,
        concurrency=report.concurrency,
        total=report.total,
        passed=report.passed,
        failed=report.failed,
        pass_rate=report.pass_rate,
        avg_latency_ms=report.avg_latency_ms,
        p95_latency_ms=report.p95_latency_ms,
        avg_attempts=report.avg_attempts,
        by_category_json=json.dumps({k: v.model_dump() for k, v in report.by_category.items()}),
        started_at=datetime.fromisoformat(report.started_at),
        finished_at=datetime.fromisoformat(report.finished_at),
    )
    session.add(run)
    await session.flush()

    for result in report.results:
        case = cases_by_id.get(result.case_id)
        prompt = case.prompt if case else "(unknown — case removed from golden.json)"
        schema_json = json.dumps(case.schema_def.model_dump()) if case else "{}"
        session.add(
            EvalCaseResult(
                eval_run_id=run.id,
                case_id=result.case_id,
                category=result.category,
                prompt=prompt,
                schema_json=schema_json,
                passed=result.passed,
                reason=result.reason,
                provider=result.provider,
                model=result.model,
                attempts=result.attempts,
                latency_ms=result.latency_ms,
                output_json=json.dumps(result.data) if result.data is not None else None,
                trace_id=result.trace_id,
            )
        )

    await session.commit()
    return run.id


async def list_runs(session: AsyncSession, *, limit: int = 20) -> list[EvalRun]:
    result = await session.scalars(select(EvalRun).order_by(EvalRun.created_at.desc()).limit(limit))
    return list(result.all())


async def get_run_detail(session: AsyncSession, run_id: str) -> EvalRunDetail:
    run = await session.scalar(select(EvalRun).where(EvalRun.id == run_id))
    if run is None:
        raise NotFoundError(f"eval run '{run_id}' not found")

    case_results = await session.scalars(
        select(EvalCaseResult)
        .where(EvalCaseResult.eval_run_id == run_id)
        .order_by(EvalCaseResult.id)
    )

    by_category_raw: dict[str, dict] = json.loads(run.by_category_json)
    results = [
        EvalCaseResultOut(
            case_id=r.case_id,
            category=r.category,
            prompt=r.prompt,
            schema_def=json.loads(r.schema_json),
            passed=r.passed,
            reason=r.reason,
            provider=r.provider,
            model=r.model,
            attempts=r.attempts,
            latency_ms=r.latency_ms,
            data=json.loads(r.output_json) if r.output_json is not None else None,
            trace_id=r.trace_id,
        )
        for r in case_results.all()
    ]

    return EvalRunDetail(
        **EvalRunSummary.model_validate(run, from_attributes=True).model_dump(),
        by_category={k: CategorySummary(**v) for k, v in by_category_raw.items()},
        results=results,
    )


def _build_leaderboard(runs: list[EvalRun]) -> list[EvalLeaderboardEntry]:
    buckets: dict[tuple[str, str | None], list[EvalRun]] = {}
    for run in runs:
        buckets.setdefault((run.provider, run.model), []).append(run)

    entries = [
        EvalLeaderboardEntry(
            provider=provider,
            model=model,
            runs=len(bucket),
            avg_pass_rate=statistics.mean(r.pass_rate for r in bucket),
            avg_latency_ms=statistics.mean(r.avg_latency_ms for r in bucket),
        )
        for (provider, model), bucket in buckets.items()
    ]
    entries.sort(key=lambda e: e.avg_pass_rate, reverse=True)
    return entries


def _build_deltas(runs: list[EvalRun]) -> EvalDeltas | None:
    if len(runs) < 2:
        return None
    latest, previous = runs[0], runs[1]
    return EvalDeltas(
        pass_rate_delta=latest.pass_rate - previous.pass_rate,
        avg_latency_ms_delta=latest.avg_latency_ms - previous.avg_latency_ms,
        p95_latency_ms_delta=latest.p95_latency_ms - previous.p95_latency_ms,
    )


async def get_dashboard(session: AsyncSession, *, history_limit: int = 50) -> EvalDashboardResponse:
    runs = await list_runs(session, limit=history_limit)
    summaries = [EvalRunSummary.model_validate(r, from_attributes=True) for r in runs]

    return EvalDashboardResponse(
        latest=summaries[0] if summaries else None,
        history=summaries,
        leaderboard=_build_leaderboard(runs),
        deltas=_build_deltas(runs),
    )
