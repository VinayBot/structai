"""Fire concurrent requests at a running StructAI server and report latency/throughput.

Registers a fresh throwaway user, then hits POST /structured/answer concurrently.
Note: this exercises the real rate limiter (RATE_LIMIT_PER_MIN) and daily quota
(DAILY_QUOTA_USER) guardrails from Phase 5 - requesting more than those limits
in a short run will surface as 429s, which is the guardrail working as intended,
not a load-test bug.

Example:
    .venv/bin/uvicorn app.main:app --port 8000 &
    python3 scripts/load_test.py --requests 20 --concurrency 5
"""

import argparse
import asyncio
import sys
import time
import uuid

import httpx

_BODY = {
    "prompt": "Say hello in one word.",
    "schema_def": {"fields": [{"name": "word", "type": "string"}]},
    "tier": "fast",
}


async def _register_and_login(client: httpx.AsyncClient, base_url: str) -> str:
    email = f"loadtest-{uuid.uuid4().hex[:10]}@example.com"
    password = "password123"
    await client.post(f"{base_url}/auth/register", json={"email": email, "password": password})
    resp = await client.post(f"{base_url}/auth/login", json={"email": email, "password": password})
    resp.raise_for_status()
    return resp.json()["access_token"]


async def _fire_one(
    client: httpx.AsyncClient, base_url: str, token: str, semaphore: asyncio.Semaphore
) -> tuple[int, float]:
    start = time.perf_counter()
    async with semaphore:
        try:
            resp = await client.post(
                f"{base_url}/structured/answer",
                json=_BODY,
                headers={"Authorization": f"Bearer {token}"},
            )
            status_code = resp.status_code
        except httpx.HTTPError:
            status_code = 0
    return status_code, (time.perf_counter() - start) * 1000


def _percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    index = min(int(len(sorted_values) * pct), len(sorted_values) - 1)
    return sorted_values[index]


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--requests", type=int, default=20)
    parser.add_argument("--concurrency", type=int, default=5)
    args = parser.parse_args()

    async with httpx.AsyncClient(timeout=60) as client:
        token = await _register_and_login(client, args.base_url)
        semaphore = asyncio.Semaphore(args.concurrency)
        start = time.perf_counter()
        results = await asyncio.gather(
            *[_fire_one(client, args.base_url, token, semaphore) for _ in range(args.requests)]
        )
        total_time = time.perf_counter() - start

    statuses = [status for status, _ in results]
    latencies = sorted(latency for _, latency in results)
    ok_count = sum(1 for status in statuses if status == 200)
    rate_limited = sum(1 for status in statuses if status == 429)

    print(f"requests:      {len(results)} (concurrency {args.concurrency})")
    print(f"wall time:     {total_time:.2f}s")
    print(f"throughput:    {len(results) / total_time:.2f} req/s")
    print(f"success (200): {ok_count}/{len(results)}")
    print(f"rate-limited:  {rate_limited}/{len(results)}")
    print(
        f"latency:       p50 {_percentile(latencies, 0.5):.0f}ms  "
        f"p95 {_percentile(latencies, 0.95):.0f}ms  max {max(latencies):.0f}ms"
    )

    return 0 if ok_count + rate_limited == len(results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
