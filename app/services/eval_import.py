import json
import logging
from collections import Counter
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.eval_run import EvalRun
from app.services.eval_service import persist_run
from eval.runner import load_cases
from eval.schemas import EvalReport, GoldenCase

logger = logging.getLogger(__name__)

REPORTS_DIR = Path("eval/reports")
CASES_PATH = Path("eval/cases/golden.json")


def _dominant_provider(report: EvalReport) -> str:
    providers = [r.provider for r in report.results if r.provider]
    if not providers:
        return "unknown"
    return Counter(providers).most_common(1)[0][0]


def _load_cases(cases_path: Path) -> list[GoldenCase]:
    if not cases_path.exists():
        return []
    return load_cases(cases_path)


async def import_existing_reports(
    session_maker: async_sessionmaker[AsyncSession],
    *,
    reports_dir: Path = REPORTS_DIR,
    cases_path: Path = CASES_PATH,
) -> int:
    """Idempotently import historical eval/reports/*.json files into the DB.

    Safe to call on every app startup: a file already imported is tracked via
    EvalRun.import_key, so re-running never creates duplicate rows. A plain
    report (no top-level provider) is imported under its dominant per-result
    provider; a compare report yields two rows, one per key ("ollama"/"groq"),
    using the known key rather than inference since a provider's results can
    be all-failed (provider=None) in a historical run.
    """
    if not reports_dir.exists():
        return 0

    cases = _load_cases(cases_path)

    async with session_maker() as session:
        existing = await session.scalars(
            select(EvalRun.import_key).where(EvalRun.import_key.is_not(None))
        )
        already_imported = set(existing.all())

        imported = 0
        for path in sorted(reports_dir.glob("*.json")):
            raw = json.loads(path.read_text())

            if "ollama" in raw and "groq" in raw:
                for provider_name in ("ollama", "groq"):
                    import_key = f"{path.name}:{provider_name}"
                    if import_key in already_imported:
                        continue
                    report = EvalReport.model_validate(raw[provider_name])
                    await persist_run(
                        session,
                        report,
                        provider=provider_name,
                        cases=cases,
                        source="imported",
                        import_key=import_key,
                    )
                    already_imported.add(import_key)
                    imported += 1
            else:
                import_key = path.name
                if import_key in already_imported:
                    continue
                report = EvalReport.model_validate(raw)
                await persist_run(
                    session,
                    report,
                    provider=_dominant_provider(report),
                    cases=cases,
                    source="imported",
                    import_key=import_key,
                )
                already_imported.add(import_key)
                imported += 1

    return imported
