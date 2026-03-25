"""
AIS load test harness — sustained-concurrent assessment scenario.

Usage
-----
    python tests/load/run_load_test.py [options]

Quick start (stack must already be running):

    # Disable the in-process rate limiter for this run:
    export RATE_LIMIT_ENABLED=false

    # Point at the target server and supply credentials:
    export AIS_BASE_URL=http://localhost:8000
    export AIS_API_KEY=your-api-key-here

    python tests/load/run_load_test.py --concurrency 50 --requests 200

Options
-------
    --url           Base URL of the AIS API   (default: $AIS_BASE_URL or http://localhost:8000)
    --api-key       API key value              (default: $AIS_API_KEY)
    --auth-header   Auth header name           (default: $AIS_AUTH_HEADER or X-API-Key)
    --concurrency   Max simultaneous requests  (default: 50)
    --requests      Total requests to send     (default: 200)
    --timeout       Per-request timeout in s   (default: 30)
    --report        Path for JSON report file  (default: artifacts/load-report.json)
    --fail-under    Min success-rate % to pass (default: 95)

Exit codes
----------
    0   success rate >= --fail-under
    1   success rate below threshold or other fatal error

Rate-limiter note
-----------------
The in-process rate limiter defaults to RATE_LIMIT_ASSESSMENTS_MAX_REQUESTS=10
per 60-second window.  A 200-request run will receive 190 HTTP 429 responses
unless you set RATE_LIMIT_ENABLED=false or raise the limit before running.

The harness counts 429 responses separately and warns loudly when they exceed
10% of total requests so you can distinguish rate-limit saturation from real
capacity issues.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx

# Resolve the project root so the script can be run from any working directory.
_HERE = Path(__file__).resolve()
_PROJECT_ROOT = _HERE.parents[2]
sys.path.insert(0, str(_PROJECT_ROOT))

from tests.load.payloads import LOAD_PAYLOADS  # noqa: E402


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_CONCURRENCY = 50
DEFAULT_TOTAL_REQUESTS = 200
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_REPORT_PATH = "artifacts/load-report.json"
DEFAULT_FAIL_UNDER = 95.0
ASSESSMENT_ENDPOINT = "/api/v1/assessments"


# ---------------------------------------------------------------------------
# Single request
# ---------------------------------------------------------------------------


async def _send_one(
    client: httpx.AsyncClient,
    payload: dict[str, Any],
    auth_header: str,
    api_key: str,
) -> dict[str, Any]:
    """Send one assessment request and return a structured result dict."""

    t0 = time.monotonic()
    try:
        response = await client.post(
            ASSESSMENT_ENDPOINT,
            json=payload,
            headers={auth_header: api_key},
        )
        elapsed = time.monotonic() - t0
        return {
            "status_code": response.status_code,
            "latency_s": elapsed,
            "ok": response.status_code == 200,
            "rate_limited": response.status_code == 429,
            "network_error": None,
        }
    except httpx.TimeoutException as exc:
        return {
            "status_code": 0,
            "latency_s": time.monotonic() - t0,
            "ok": False,
            "rate_limited": False,
            "network_error": f"timeout: {exc}",
        }
    except httpx.RequestError as exc:
        return {
            "status_code": 0,
            "latency_s": time.monotonic() - t0,
            "ok": False,
            "rate_limited": False,
            "network_error": str(exc),
        }


# ---------------------------------------------------------------------------
# Concurrent runner
# ---------------------------------------------------------------------------


async def run(
    *,
    base_url: str,
    api_key: str,
    auth_header: str,
    concurrency: int,
    total_requests: int,
    timeout_seconds: float,
) -> tuple[list[dict[str, Any]], float]:
    """Issue ``total_requests`` POSTs with at most ``concurrency`` in-flight."""

    limits = httpx.Limits(
        max_connections=concurrency,
        max_keepalive_connections=concurrency,
    )
    semaphore = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(
        base_url=base_url,
        timeout=timeout_seconds,
        limits=limits,
    ) as client:

        async def _bounded(index: int) -> dict[str, Any]:
            payload = LOAD_PAYLOADS[index % len(LOAD_PAYLOADS)]
            async with semaphore:
                return await _send_one(client, payload, auth_header, api_key)

        t_start = time.monotonic()
        results = await asyncio.gather(*[_bounded(i) for i in range(total_requests)])
        wall_elapsed = time.monotonic() - t_start

    return list(results), wall_elapsed


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def _percentile(sorted_values: list[float], pct: float) -> float | None:
    if not sorted_values:
        return None
    idx = min(int(len(sorted_values) * pct / 100), len(sorted_values) - 1)
    return round(sorted_values[idx], 4)


def compute_metrics(results: list[dict[str, Any]], wall_elapsed: float) -> dict[str, Any]:
    """Reduce raw result dicts to a flat metrics summary."""

    total = len(results)
    ok = sum(1 for r in results if r["ok"])
    rate_limited = sum(1 for r in results if r["rate_limited"])
    network_errors = sum(1 for r in results if r["network_error"] is not None)
    other_failures = total - ok - rate_limited - network_errors

    ok_latencies = sorted(r["latency_s"] for r in results if r["ok"])

    return {
        "scenario": "sustained-concurrent",
        "total_requests": total,
        "successful_2xx": ok,
        "rate_limited_429": rate_limited,
        "network_errors": network_errors,
        "other_failures": other_failures,
        "success_rate_pct": round(ok / total * 100, 2) if total else 0.0,
        "wall_elapsed_s": round(wall_elapsed, 3),
        "throughput_rps": round(total / wall_elapsed, 2) if wall_elapsed > 0 else 0.0,
        "latency_s": {
            "min": round(min(ok_latencies), 4) if ok_latencies else None,
            "p50": _percentile(ok_latencies, 50),
            "p75": _percentile(ok_latencies, 75),
            "p95": _percentile(ok_latencies, 95),
            "p99": _percentile(ok_latencies, 99),
            "max": round(max(ok_latencies), 4) if ok_latencies else None,
            "sample_count": len(ok_latencies),
        },
    }


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def _hr(char: str = "-", width: int = 52) -> str:
    return char * width


def print_summary(metrics: dict[str, Any], config: dict[str, Any]) -> None:
    """Print a human-readable summary to stdout."""

    rate_limit_pct = (
        metrics["rate_limited_429"] / metrics["total_requests"] * 100
        if metrics["total_requests"]
        else 0.0
    )
    warn_rate_limit = rate_limit_pct > 10

    print()
    print("AIS Load Test")
    print(_hr("="))
    print(f"  Scenario    : {metrics['scenario']}")
    print(f"  URL         : {config['base_url']}{ASSESSMENT_ENDPOINT}")
    print(f"  Payloads    : {len(LOAD_PAYLOADS)} deterministic fixtures (round-robin)")
    print(f"  Concurrency : {config['concurrency']} simultaneous workers")
    print(f"  Total reqs  : {config['total_requests']}")
    print()
    print("Results")
    print(_hr())
    print(f"  Successful (2xx)  : {metrics['successful_2xx']:>6} / {metrics['total_requests']}"
          f"  ({metrics['success_rate_pct']:.1f}%)")
    print(f"  Rate-limited (429): {metrics['rate_limited_429']:>6}  ({rate_limit_pct:.1f}%)")
    print(f"  Network errors    : {metrics['network_errors']:>6}")
    print(f"  Other failures    : {metrics['other_failures']:>6}")
    print(f"  Elapsed           : {metrics['wall_elapsed_s']:.3f} s")
    print(f"  Throughput        : {metrics['throughput_rps']:.1f} req/s")

    lat = metrics["latency_s"]
    if lat.get("sample_count", 0) > 0:
        print()
        print("Latency (successful requests)")
        print(_hr())
        print(f"  min : {lat['min']:.4f} s")
        print(f"  p50 : {lat['p50']:.4f} s")
        print(f"  p75 : {lat['p75']:.4f} s")
        print(f"  p95 : {lat['p95']:.4f} s")
        print(f"  p99 : {lat['p99']:.4f} s")
        print(f"  max : {lat['max']:.4f} s")
        print(f"  n   : {lat['sample_count']}")

    if warn_rate_limit:
        print()
        print("  *** WARNING: {:.1f}% of requests were rate-limited (HTTP 429). ***".format(
            rate_limit_pct
        ))
        print("  Set RATE_LIMIT_ENABLED=false before running to measure real capacity.")

    print()


def write_report(metrics: dict[str, Any], config: dict[str, Any], path: str) -> None:
    """Write a machine-readable JSON report to *path*."""

    report = {"config": config, "metrics": metrics}
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2))
    print(f"  Report written to: {output_path}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AIS load test — sustained-concurrent assessment scenario",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--url",
        default=os.environ.get("AIS_BASE_URL", DEFAULT_BASE_URL),
        help="Base URL of the AIS API (default: $AIS_BASE_URL or http://localhost:8000)",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("AIS_API_KEY", ""),
        dest="api_key",
        help="API key value (default: $AIS_API_KEY)",
    )
    parser.add_argument(
        "--auth-header",
        default=os.environ.get("AIS_AUTH_HEADER", "X-API-Key"),
        dest="auth_header",
        help="Auth header name (default: $AIS_AUTH_HEADER or X-API-Key)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=DEFAULT_CONCURRENCY,
        help=f"Max simultaneous requests (default: {DEFAULT_CONCURRENCY})",
    )
    parser.add_argument(
        "--requests",
        type=int,
        default=DEFAULT_TOTAL_REQUESTS,
        dest="total_requests",
        help=f"Total requests to send (default: {DEFAULT_TOTAL_REQUESTS})",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Per-request timeout in seconds (default: {DEFAULT_TIMEOUT_SECONDS})",
    )
    parser.add_argument(
        "--report",
        default=DEFAULT_REPORT_PATH,
        help=f"Path for JSON report file (default: {DEFAULT_REPORT_PATH})",
    )
    parser.add_argument(
        "--fail-under",
        type=float,
        default=DEFAULT_FAIL_UNDER,
        dest="fail_under",
        help=f"Minimum success-rate %% to exit 0 (default: {DEFAULT_FAIL_UNDER})",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    if not args.api_key:
        print(
            "Error: --api-key or $AIS_API_KEY is required.\n"
            "Example: export AIS_API_KEY=your-key && python tests/load/run_load_test.py",
            file=sys.stderr,
        )
        return 1

    config = {
        "base_url": args.url,
        "auth_header": args.auth_header,
        "concurrency": args.concurrency,
        "total_requests": args.total_requests,
        "timeout_s": args.timeout,
        "fail_under_pct": args.fail_under,
        "payload_count": len(LOAD_PAYLOADS),
    }

    print(f"Starting: {config['total_requests']} requests, "
          f"{config['concurrency']} concurrent → {args.url}{ASSESSMENT_ENDPOINT}")

    results, wall_elapsed = asyncio.run(
        run(
            base_url=args.url,
            api_key=args.api_key,
            auth_header=args.auth_header,
            concurrency=args.concurrency,
            total_requests=args.total_requests,
            timeout_seconds=args.timeout,
        )
    )

    metrics = compute_metrics(results, wall_elapsed)
    print_summary(metrics, config)
    write_report(metrics, config, args.report)

    if metrics["success_rate_pct"] < args.fail_under:
        print(
            f"  FAIL: success rate {metrics['success_rate_pct']:.1f}% "
            f"is below --fail-under {args.fail_under:.1f}%",
            file=sys.stderr,
        )
        return 1

    print(f"  PASS: success rate {metrics['success_rate_pct']:.1f}% "
          f">= --fail-under {args.fail_under:.1f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
