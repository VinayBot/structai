import asyncio
import json
import statistics
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from app.core.logging import request_id_ctx
from app.core.stats import percentile
from app.gateway.router import GatewayError, ModelGateway
from app.services.structured_service import StructuredAnswerError, answer
from eval.schemas import CaseResult, CategorySummary, EvalReport, ExpectedCheck, GoldenCase


def load_cases(path: Path) -> list[GoldenCase]:
    raw = json.loads(path.read_text())
    return [GoldenCase.model_validate(c) for c in raw]


def _texts_equal(actual: str, expected: str) -> bool:
    try:
        return float(actual) == float(expected)
    except ValueError:
        return actual == expected


def check_result(data: dict, checks: list[ExpectedCheck]) -> tuple[bool, str | None]:
    for check in checks:
        if check.field not in data:
            return False, f"missing field '{check.field}'"
        value = data[check.field]
        text = str(value).strip().lower()

        if check.equals is not None and not _texts_equal(text, check.equals.strip().lower()):
            return False, f"{check.field}: expected '{check.equals}', got '{value}'"
        if check.contains is not None and check.contains.strip().lower() not in text:
            return False, f"{check.field}: expected to contain '{check.contains}', got '{value}'"
        if check.one_of is not None:
            allowed = {o.strip().lower() for o in check.one_of}
            if text not in allowed:
                return False, f"{check.field}: '{value}' not in allowed set {check.one_of}"

    return True, None


async def run_case(
    gateway: ModelGateway,
    case: GoldenCase,
    *,
    semaphore: asyncio.Semaphore,
    timeout: float = 30.0,
    max_attempts: int = 3,
    clock: Callable[[], float] = time.perf_counter,
) -> CaseResult:
    start = clock()
    async with semaphore:
        try:
            result = await answer(
                gateway,
                prompt=case.prompt,
                schema=case.schema_def,
                tier=case.tier,
                max_attempts=max_attempts,
                timeout=timeout,
            )
        except (StructuredAnswerError, GatewayError) as exc:
            return CaseResult(
                case_id=case.id,
                category=case.category,
                passed=False,
                reason=str(exc),
                latency_ms=(clock() - start) * 1000,
            )

    passed, reason = check_result(result.data, case.checks)
    return CaseResult(
        case_id=case.id,
        category=case.category,
        passed=passed,
        reason=reason,
        provider=result.provider,
        model=result.model,
        attempts=result.attempts,
        latency_ms=(clock() - start) * 1000,
        data=result.data,
    )


async def run_case_traced(
    gateway: ModelGateway,
    case: GoldenCase,
    *,
    semaphore: asyncio.Semaphore,
    timeout: float = 30.0,
    max_attempts: int = 3,
    clock: Callable[[], float] = time.perf_counter,
) -> CaseResult:
    """Like `run_case`, but gives this case its own trace id.

    `asyncio.create_task`/`asyncio.gather` each copy the *current* context, so a
    `request_id_ctx.set()` made here only affects this task's own copy, not sibling
    case-tasks running concurrently in the same eval run.
    """
    trace_id = uuid.uuid4().hex[:16]
    request_id_ctx.set(trace_id)
    result = await run_case(
        gateway, case, semaphore=semaphore, timeout=timeout, max_attempts=max_attempts, clock=clock
    )
    return result.model_copy(update={"trace_id": trace_id})


def summarize_results(
    results: list[CaseResult],
    *,
    concurrency: int,
    started_at: datetime,
    finished_at: datetime,
) -> EvalReport:
    passed = sum(1 for r in results if r.passed)
    latencies = sorted(r.latency_ms for r in results)
    attempts = [r.attempts for r in results if r.attempts is not None]

    by_category: dict[str, CategorySummary] = {}
    for result in results:
        summary = by_category.setdefault(result.category, CategorySummary(total=0, passed=0))
        summary.total += 1
        if result.passed:
            summary.passed += 1

    return EvalReport(
        started_at=started_at.isoformat(),
        finished_at=finished_at.isoformat(),
        concurrency=concurrency,
        total=len(results),
        passed=passed,
        failed=len(results) - passed,
        pass_rate=passed / len(results) if results else 0.0,
        avg_latency_ms=statistics.mean(latencies) if latencies else 0.0,
        p95_latency_ms=percentile(latencies, 0.95),
        avg_attempts=statistics.mean(attempts) if attempts else 0.0,
        by_category=by_category,
        results=list(results),
    )


async def run_eval(
    cases: list[GoldenCase],
    gateway: ModelGateway,
    *,
    concurrency: int = 5,
    timeout: float = 30.0,
    max_attempts: int = 3,
    clock: Callable[[], float] = time.perf_counter,
    wall_clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> EvalReport:
    started_at = wall_clock()
    semaphore = asyncio.Semaphore(concurrency)
    results = await asyncio.gather(
        *[
            run_case_traced(
                gateway,
                case,
                semaphore=semaphore,
                timeout=timeout,
                max_attempts=max_attempts,
                clock=clock,
            )
            for case in cases
        ]
    )
    finished_at = wall_clock()

    return summarize_results(
        list(results), concurrency=concurrency, started_at=started_at, finished_at=finished_at
    )
