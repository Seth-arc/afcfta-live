"""
AIS multi-worker throughput comparison harness.

Runs the burst load scenario against two separately started server instances
(single-worker and multi-worker) and prints a side-by-side comparison.

This script is a measurement harness only.  It does not start or stop
server processes.  Start both servers before running this script.

Usage
-----
Start a single-worker server on port 8001 and a multi-worker server on
port 8002 (see docs/dev/testing.md for exact commands), then run:

    python tests/load/run_multi_worker_comparison.py \\
        --single-url http://localhost:8001 \\
        --multi-url  http://localhost:8002 \\
        --api-key    $AIS_API_KEY

Options
-------
    --single-url        URL of the single-worker server   (default: http://localhost:8001)
    --multi-url         URL of the multi-worker server    (default: http://localhost:8002)
    --api-key           API key value                     (default: $AIS_API_KEY)
    --auth-header       Auth header name                  (default: X-API-Key)
    --concurrency       Simultaneous workers per run      (default: 50)
    --requests          Total requests per run            (default: 200)
    --timeout           Per-request timeout in seconds    (default: 30)
    --report            Output JSON report path           (default: artifacts/multi-worker-comparison.json)

Exit codes
----------
    0   Comparison completed successfully.
    1   One or both runs failed the success-rate threshold or a fatal error occurred.

Rate-limiter note
-----------------
Set RATE_LIMIT_ENABLED=false on both servers before running.
The default limit of 10 assessments per 60 s will saturate a 200-request run.
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

_HERE = Path(__file__).resolve()
_PROJECT_ROOT = _HERE.parents[2]
sys.path.insert(0, str(_PROJECT_ROOT))

from tests.load.payloads import LOAD_PAYLOADS  # noqa: E402
from tests.load.run_load_test import (  # noqa: E402
    compute_metrics,
    run,
)

ASSESSMENT_ENDPOINT = "/api/v1/assessments"
DEFAULT_SINGLE_URL = "http://localhost:8001"
DEFAULT_MULTI_URL = "http://localhost:8002"
DEFAULT_CONCURRENCY = 50
DEFAULT_TOTAL_REQUESTS = 200
DEFAULT_TIMEOUT = 30.0
DEFAULT_REPORT = "artifacts/multi-worker-comparison.json"
MIN_SUCCESS_RATE = 95.0


# ---------------------------------------------------------------------------
# Comparison helpers
# ---------------------------------------------------------------------------


def _delta_pct(baseline: float | None, current: float | None) -> str:
    """Format the relative change from baseline to current as a percentage string."""
    if baseline is None or current is None or baseline == 0:
        return "n/a"
    delta = (current - baseline) / baseline * 100
    sign = "+" if delta >= 0 else ""
    return f"{sign}{delta:.1f}%"


def build_comparison(
    single: dict[str, Any],
    multi: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Build the side-by-side comparison payload written to the report file."""

    sm = single["metrics"]
    mm = multi["metrics"]

    sl = sm["latency_s"]
    ml = mm["latency_s"]

    return {
        "config": config,
        "single_worker": single,
        "multi_worker": multi,
        "comparison": {
            "throughput_rps": {
                "single": sm["throughput_rps"],
                "multi": mm["throughput_rps"],
                "delta_pct": _delta_pct(sm["throughput_rps"], mm["throughput_rps"]),
            },
            "success_rate_pct": {
                "single": sm["success_rate_pct"],
                "multi": mm["success_rate_pct"],
                "delta_pct": _delta_pct(sm["success_rate_pct"], mm["success_rate_pct"]),
            },
            "latency_p50_s": {
                "single": sl["p50"],
                "multi": ml["p50"],
                "delta_pct": _delta_pct(sl["p50"], ml["p50"]),
            },
            "latency_p95_s": {
                "single": sl["p95"],
                "multi": ml["p95"],
                "delta_pct": _delta_pct(sl["p95"], ml["p95"]),
            },
            "latency_p99_s": {
                "single": sl["p99"],
                "multi": ml["p99"],
                "delta_pct": _delta_pct(sl["p99"], ml["p99"]),
            },
        },
    }


def print_comparison(report: dict[str, Any]) -> None:
    """Print a human-readable side-by-side table to stdout."""

    cfg = report["config"]
    cmp = report["comparison"]

    hr_eq = "=" * 60
    hr_dash = "-" * 60

    print()
    print("AIS Multi-Worker Throughput Comparison")
    print(hr_eq)
    print(f"  Single-worker URL : {cfg['single_url']}")
    print(f"  Multi-worker URL  : {cfg['multi_url']}")
    print(f"  Concurrency       : {cfg['concurrency']} simultaneous workers")
    print(f"  Total requests    : {cfg['total_requests']} per run")
    print(f"  Payloads          : {len(LOAD_PAYLOADS)} deterministic fixtures (round-robin)")
    print()

    col_w = 12
    print(f"  {'Metric':<28} {'Single':>{col_w}} {'Multi':>{col_w}} {'Delta':>{col_w}}")
    print("  " + hr_dash)

    rows = [
        ("throughput (req/s)",  cmp["throughput_rps"]["single"],
         cmp["throughput_rps"]["multi"],  cmp["throughput_rps"]["delta_pct"]),
        ("success rate (%)",    cmp["success_rate_pct"]["single"],
         cmp["success_rate_pct"]["multi"], cmp["success_rate_pct"]["delta_pct"]),
        ("p50 latency (s)",     cmp["latency_p50_s"]["single"],
         cmp["latency_p50_s"]["multi"],   cmp["latency_p50_s"]["delta_pct"]),
        ("p95 latency (s)",     cmp["latency_p95_s"]["single"],
         cmp["latency_p95_s"]["multi"],   cmp["latency_p95_s"]["delta_pct"]),
        ("p99 latency (s)",     cmp["latency_p99_s"]["single"],
         cmp["latency_p99_s"]["multi"],   cmp["latency_p99_s"]["delta_pct"]),
    ]

    for label, single_val, multi_val, delta in rows:
        sv = f"{single_val:.4f}" if isinstance(single_val, float) else str(single_val)
        mv = f"{multi_val:.4f}" if isinstance(multi_val, float) else str(multi_val)
        print(f"  {label:<28} {sv:>{col_w}} {mv:>{col_w}} {delta:>{col_w}}")

    print()

    sm = report["single_worker"]["metrics"]
    mm = report["multi_worker"]["metrics"]
    if sm["rate_limited_429"] or mm["rate_limited_429"]:
        print("  *** WARNING: rate-limited responses detected.")
        print("      Set RATE_LIMIT_ENABLED=false on both servers before re-running. ***")
        print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AIS multi-worker throughput comparison",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--single-url",
        default=DEFAULT_SINGLE_URL,
        dest="single_url",
        help=f"Base URL of the single-worker server (default: {DEFAULT_SINGLE_URL})",
    )
    parser.add_argument(
        "--multi-url",
        default=DEFAULT_MULTI_URL,
        dest="multi_url",
        help=f"Base URL of the multi-worker server (default: {DEFAULT_MULTI_URL})",
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
        help="Auth header name (default: X-API-Key)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=DEFAULT_CONCURRENCY,
        help=f"Simultaneous workers per run (default: {DEFAULT_CONCURRENCY})",
    )
    parser.add_argument(
        "--requests",
        type=int,
        default=DEFAULT_TOTAL_REQUESTS,
        dest="total_requests",
        help=f"Total requests per run (default: {DEFAULT_TOTAL_REQUESTS})",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"Per-request timeout in seconds (default: {DEFAULT_TIMEOUT})",
    )
    parser.add_argument(
        "--report",
        default=DEFAULT_REPORT,
        help=f"Output JSON report path (default: {DEFAULT_REPORT})",
    )
    return parser.parse_args()


def _run_one(
    *,
    label: str,
    url: str,
    api_key: str,
    auth_header: str,
    concurrency: int,
    total_requests: int,
    timeout: float,
) -> tuple[dict[str, Any], bool]:
    """Run one burst scenario and return (report_dict, passed)."""

    print(f"  [{label}] Starting: {total_requests} requests, "
          f"{concurrency} concurrent -> {url}{ASSESSMENT_ENDPOINT}")

    try:
        results, wall_elapsed = asyncio.run(
            run(
                base_url=url,
                api_key=api_key,
                auth_header=auth_header,
                concurrency=concurrency,
                total_requests=total_requests,
                timeout_seconds=timeout,
            )
        )
    except httpx.ConnectError as exc:
        print(f"  [{label}] FATAL: cannot connect to {url} — {exc}", file=sys.stderr)
        print(f"  Is the {label} server running?", file=sys.stderr)
        return {}, False

    metrics = compute_metrics(results, wall_elapsed)
    passed = metrics["success_rate_pct"] >= MIN_SUCCESS_RATE

    rl_pct = (
        metrics["rate_limited_429"] / metrics["total_requests"] * 100
        if metrics["total_requests"] else 0.0
    )
    status = "PASS" if passed else "FAIL"
    print(
        f"  [{label}] {status}  "
        f"rps={metrics['throughput_rps']:.1f}  "
        f"p95={metrics['latency_s']['p95']:.4f}s  "
        f"success={metrics['success_rate_pct']:.1f}%"
        + (f"  *** {rl_pct:.0f}% rate-limited ***" if rl_pct > 10 else "")
    )

    report = {
        "label": label,
        "url": url,
        "metrics": metrics,
    }
    return report, passed


def main() -> int:
    args = _parse_args()

    if not args.api_key:
        print(
            "Error: --api-key or $AIS_API_KEY is required.",
            file=sys.stderr,
        )
        return 1

    config = {
        "single_url": args.single_url,
        "multi_url": args.multi_url,
        "concurrency": args.concurrency,
        "total_requests": args.total_requests,
        "timeout_s": args.timeout,
        "payload_count": len(LOAD_PAYLOADS),
    }

    print()
    print("AIS Multi-Worker Comparison — measuring both servers ...")
    print("-" * 60)

    single_report, single_ok = _run_one(
        label="single-worker",
        url=args.single_url,
        api_key=args.api_key,
        auth_header=args.auth_header,
        concurrency=args.concurrency,
        total_requests=args.total_requests,
        timeout=args.timeout,
    )
    if not single_ok and not single_report:
        return 1

    # Brief pause so the DB connection pool stabilises between runs.
    time.sleep(2)

    multi_report, multi_ok = _run_one(
        label="multi-worker",
        url=args.multi_url,
        api_key=args.api_key,
        auth_header=args.auth_header,
        concurrency=args.concurrency,
        total_requests=args.total_requests,
        timeout=args.timeout,
    )
    if not multi_ok and not multi_report:
        return 1

    comparison = build_comparison(single_report, multi_report, config)
    print_comparison(comparison)

    output_path = Path(args.report)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(comparison, indent=2))
    print(f"  Report written to: {output_path}")
    print()

    if not single_ok or not multi_ok:
        print(
            "  FAIL: one or both runs fell below the 95 % success-rate threshold.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
