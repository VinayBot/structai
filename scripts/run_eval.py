"""Run the golden-case evaluation harness against the model gateway.

Examples:
    python3 scripts/run_eval.py
    python3 scripts/run_eval.py --provider ollama --concurrency 3
    python3 scripts/run_eval.py --compare
"""

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from app.config import get_settings
from app.gateway.factory import build_gateway, build_single_provider_gateway
from eval.runner import load_cases, run_eval
from eval.schemas import EvalReport


def _print_report(label: str, report: EvalReport) -> None:
    print(f"\n=== {label} ===")
    print(f"pass rate:    {report.passed}/{report.total} ({report.pass_rate:.0%})")
    print(f"avg latency:  {report.avg_latency_ms:.0f}ms  (p95 {report.p95_latency_ms:.0f}ms)")
    print(f"avg attempts: {report.avg_attempts:.2f}")
    print(f"{'category':<16}{'passed':>10}")
    for category, summary in sorted(report.by_category.items()):
        print(f"{category:<16}{summary.passed:>6}/{summary.total:<3}")

    failures = [r for r in report.results if not r.passed]
    if failures:
        print("\nfailures:")
        for r in failures:
            print(f"  - {r.case_id}: {r.reason}")


def _print_comparison(reports: dict[str, EvalReport]) -> None:
    print("\n=== model comparison ===")
    print(f"{'provider':<10}{'pass rate':>12}{'avg ms':>10}{'p95 ms':>10}{'avg attempts':>14}")
    for name, report in reports.items():
        print(
            f"{name:<10}{report.pass_rate:>11.0%}{report.avg_latency_ms:>10.0f}"
            f"{report.p95_latency_ms:>10.0f}{report.avg_attempts:>14.2f}"
        )


def _write_report(data: dict, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=2))
    print(f"\nreport written to {out_path}")


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", default="eval/cases/golden.json")
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument(
        "--provider",
        choices=["gateway", "ollama", "groq"],
        default="gateway",
        help="'gateway' uses the configured ollama->groq fallback chain (default)",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="run ollama and groq separately and print a side-by-side comparison",
    )
    parser.add_argument("--out", default=None, help="path for the JSON report")
    args = parser.parse_args()

    settings = get_settings()
    cases = load_cases(Path(args.cases))
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    if args.compare:
        reports: dict[str, EvalReport] = {}
        for name in ("ollama", "groq"):
            gateway = build_single_provider_gateway(name, settings)
            reports[name] = await run_eval(
                cases,
                gateway,
                concurrency=args.concurrency,
                timeout=args.timeout,
                max_attempts=args.max_attempts,
            )
            _print_report(name, reports[name])
        _print_comparison(reports)
        out_path = Path(args.out) if args.out else Path("eval/reports") / f"compare-{ts}.json"
        _write_report({name: r.model_dump() for name, r in reports.items()}, out_path)
        return 0 if all(r.failed == 0 for r in reports.values()) else 1

    if args.provider == "gateway":
        gateway = build_gateway(settings)
    else:
        gateway = build_single_provider_gateway(args.provider, settings)
    report = await run_eval(
        cases,
        gateway,
        concurrency=args.concurrency,
        timeout=args.timeout,
        max_attempts=args.max_attempts,
    )
    _print_report(args.provider, report)
    out_path = Path(args.out) if args.out else Path("eval/reports") / f"{ts}.json"
    _write_report(report.model_dump(), out_path)
    return 0 if report.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
