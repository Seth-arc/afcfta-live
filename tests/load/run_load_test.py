"""
AIS load test harness — burst and ramp-profile scenarios.

Usage
-----
    python tests/load/run_load_test.py [options]

Quick start (stack must already be running):

    # Disable the in-process rate limiter for this run:
    export RATE_LIMIT_ENABLED=false

    # Point at the target server and supply credentials:
    export AIS_BASE_URL=http://localhost:8000
    export AIS_API_KEY=your-api-key-here

    # Burst mode (all workers at once — existing behaviour):
    python tests/load/run_load_test.py --mode burst --concurrency 50 --requests 200

    # Ramp mode (concurrency increases in steps over time):
    python tests/load/run_load_test.py --mode ramp \
        --ramp-stages 10,25,50 --ramp-stage-duration 20

Modes
-----
    burst   All workers launch simultaneously.  Controlled by --concurrency and
            --requests.  This is the original behaviour.

    ramp    Concurrency increases in discrete steps.  Each step runs for a fixed
            wall-clock window before the next step starts.  Controlled by
            --ramp-stages and --ramp-stage-duration.

Options
-------
    --mode              "burst" or "ramp"          (default: burst)
    --url               Base URL of the AIS API    (default: $AIS_BASE_URL or http://localhost:8000)
    --api-key           API key value              (default: $AIS_API_KEY)
    --auth-header       Auth header name           (default: $AIS_AUTH_HEADER or X-API-Key)
    --concurrency       [burst] Max simultaneous   (default: 50)
    --requests          [burst] Total to send      (default: 200)
    --timeout           Per-request timeout in s   (default: 30)
    --report            Path for JSON report       (default: artifacts/load-report.json)
    --fail-under        Min success-rate % to pass (default: 95)
    --ramp-stages       [ramp] Comma-separated concurrency levels
                                                   (default: 10,25,50)
    --ramp-stage-duration [ramp] Seconds per stage (default: 20)

Exit codes
----------
    0   Overall success rate >= --fail-under
    1   Overall success rate below threshold or other fatal error

Rate-limiter note
-----------------
The in-process rate limiter defaults to RATE_LIMIT_ASSESSMENTS_MAX_REQUESTS=10
per 60-second window.  A 200-request burst run will receive 190 HTTP 429 responses
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
DEFAULT_MODE = "burst"
DEFAULT_CONCURRENCY = 50
DEFAULT_TOTAL_REQUESTS = 200
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_REPORT_PATH = "artifacts/load-report.json"
DEFAULT_FAIL_UNDER = 95.0
DEFAULT_RAMP_STAGES = "10,25,50"
DEFAULT_RAMP_STAGE_DURATION = 20
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
# Burst runner (original behaviour)
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
# Ramp runner
# ---------------------------------------------------------------------------


async def _run_one_stage(
    *,
    client: httpx.AsyncClient,
    concurrency: int,
    duration_seconds: float,
    auth_header: str,
    api_key: str,
) -> tuple[list[dict[str, Any]], float]:
    """Drive requests at ``concurrency`` for ``duration_seconds`` wall-clock seconds.

    Requests are dispatched as fast as the concurrency limit allows.  When the stage
    window expires, no new requests are started but any in-flight requests are allowed
    to complete so metrics are not skewed by abandoned connections.
    """

    results: list[dict[str, Any]] = []
    stage_start = time.monotonic()
    stage_end = stage_start + duration_seconds
    request_index = 0

    async def _worker(idx: int) -> None:
        payload = LOAD_PAYLOADS[idx % len(LOAD_PAYLOADS)]
        result = await _send_one(client, payload, auth_header, api_key)
        results.append(result)

    # Seed with a full concurrency batch to reach the target load immediately.
    active: set[asyncio.Task] = set()
    for _ in range(concurrency):
        task = asyncio.create_task(_worker(request_index))
        request_index += 1
        active.add(task)

    while active:
        done, active = await asyncio.wait(active, return_when=asyncio.FIRST_COMPLETED)

        if time.monotonic() < stage_end:
            # Refill to maintain the target concurrency level.
            for _ in range(len(done)):
                if time.monotonic() >= stage_end:
                    break
                task = asyncio.create_task(_worker(request_index))
                request_index += 1
                active.add(task)
        # When stage_end is reached, done tasks drain naturally and no new ones are
        # added, so active will eventually become empty and the loop exits.

    wall_elapsed = time.monotonic() - stage_start
    return results, wall_elapsed


async def run_ramp(
    *,
    base_url: str,
    api_key: str,
    auth_header: str,
    stage_concurrencies: list[int],
    stage_duration_seconds: float,
    timeout_seconds: float,
) -> list[dict[str, Any]]:
    """Run the ramp scenario and return a list of per-stage raw result bundles.

    Each bundle is a dict::

        {
            "stage":            int,        # 1-based stage number
            "concurrency":      int,        # target concurrency for this stage
            "duration_target_s": float,     # configured window
            "results":          list[dict], # one dict per request (from _send_one)
            "wall_elapsed_s":   float,      # actual stage elapsed including drain
        }

    A single ``httpx.AsyncClient`` is shared across all stages so the connection pool
    reflects a steady-state server rather than a cold-start per stage.
    """

    max_concurrency = max(stage_concurrencies)
    limits = httpx.Limits(
        max_connections=max_concurrency,
        max_keepalive_connections=max_concurrency,
    )

    stage_bundles: list[dict[str, Any]] = []

    async with httpx.AsyncClient(
        base_url=base_url,
        timeout=timeout_seconds,
        limits=limits,
    ) as client:
        for stage_num, concurrency in enumerate(stage_concurrencies, start=1):
            stage_results, elapsed = await _run_one_stage(
                client=client,
                concurrency=concurrency,
                duration_seconds=stage_duration_seconds,
                auth_header=auth_header,
                api_key=api_key,
            )
            stage_bundles.append(
                {
                    "stage": stage_num,
                    "concurrency": concurrency,
                    "duration_target_s": stage_duration_seconds,
                    "results": stage_results,
                    "wall_elapsed_s": elapsed,
                }
            )

    return stage_bundles


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


def compute_stage_metrics(bundle: dict[str, Any]) -> dict[str, Any]:
    """Compute metrics for one ramp stage and attach stage metadata."""

    metrics = compute_metrics(bundle["results"], bundle["wall_elapsed_s"])
    metrics["scenario"] = "ramp-stage"
    return {
        "stage": bundle["stage"],
        "concurrency": bundle["concurrency"],
        "duration_target_s": bundle["duration_target_s"],
        "wall_elapsed_s": metrics.pop("wall_elapsed_s"),
        **metrics,
    }


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def _hr(char: str = "-", width: int = 52) -> str:
    return char * width


def _print_latency(lat: dict[str, Any]) -> None:
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


def print_summary(
    metrics: dict[str, Any],
    config: dict[str, Any],
    *,
    stage_metrics: list[dict[str, Any]] | None = None,
) -> None:
    """Print a human-readable summary to stdout."""

    rate_limit_pct = (
        metrics["rate_limited_429"] / metrics["total_requests"] * 100
        if metrics["total_requests"]
        else 0.0
    )
    warn_rate_limit = rate_limit_pct > 10

    mode = config.get("mode", "burst")

    print()
    print("AIS Load Test")
    print(_hr("="))
    print(f"  Mode        : {mode}")
    print(f"  URL         : {config['base_url']}{ASSESSMENT_ENDPOINT}")
    print(f"  Payloads    : {len(LOAD_PAYLOADS)} deterministic fixtures (round-robin)")

    if mode == "ramp" and stage_metrics:
        stages = config.get("ramp_stages", [])
        duration = config.get("ramp_stage_duration_s", "?")
        print(f"  Stages      : {len(stages)} x {duration}s "
              f"({', '.join(str(c) for c in stages)} concurrent workers)")
    else:
        print(f"  Concurrency : {config['concurrency']} simultaneous workers")
        print(f"  Total reqs  : {config['total_requests']}")

    if mode == "ramp" and stage_metrics:
        print()
        print("Per-Stage Results")
        print(_hr("="))
        for sm in stage_metrics:
            rl_pct = (
                sm["rate_limited_429"] / sm["total_requests"] * 100
                if sm["total_requests"] else 0.0
            )
            p95 = sm["latency_s"]["p95"]
            p95_str = f"{p95:.4f}s" if p95 is not None else "n/a"
            print(
                f"  Stage {sm['stage']:>2}  "
                f"concurrency={sm['concurrency']:>3}  "
                f"reqs={sm['total_requests']:>5}  "
                f"ok={sm['successful_2xx']:>5}  "
                f"({sm['success_rate_pct']:.1f}%)  "
                f"p95={p95_str}  "
                f"rps={sm['throughput_rps']:.1f}"
                + (f"  *** {rl_pct:.0f}% rate-limited ***" if rl_pct > 10 else "")
            )

        print()
        print("Aggregate Results")
        print(_hr())
    else:
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

    _print_latency(metrics["latency_s"])

    if warn_rate_limit:
        print()
        print("  *** WARNING: {:.1f}% of requests were rate-limited (HTTP 429). ***".format(
            rate_limit_pct
        ))
        print("  Set RATE_LIMIT_ENABLED=false before running to measure real capacity.")

    print()


def write_report(
    metrics: dict[str, Any],
    config: dict[str, Any],
    path: str,
    *,
    stage_metrics: list[dict[str, Any]] | None = None,
) -> None:
    """Write a machine-readable JSON report to *path*."""

    report: dict[str, Any] = {"config": config, "mode": config.get("mode", "burst"),
                               "metrics": metrics}
    if stage_metrics is not None:
        report["stages"] = stage_metrics

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2))
    print(f"  Report written to: {output_path}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AIS load test — burst and ramp-profile scenarios",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--mode",
        choices=["burst", "ramp"],
        default=DEFAULT_MODE,
        help=f"'burst' launches all workers at once; 'ramp' increases concurrency in steps "
             f"(default: {DEFAULT_MODE})",
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
    # Burst-mode args
    parser.add_argument(
        "--concurrency",
        type=int,
        default=DEFAULT_CONCURRENCY,
        help=f"[burst] Max simultaneous requests (default: {DEFAULT_CONCURRENCY})",
    )
    parser.add_argument(
        "--requests",
        type=int,
        default=DEFAULT_TOTAL_REQUESTS,
        dest="total_requests",
        help=f"[burst] Total requests to send (default: {DEFAULT_TOTAL_REQUESTS})",
    )
    # Ramp-mode args
    parser.add_argument(
        "--ramp-stages",
        default=DEFAULT_RAMP_STAGES,
        dest="ramp_stages",
        help=f"[ramp] Comma-separated concurrency levels per stage "
             f"(default: {DEFAULT_RAMP_STAGES})",
    )
    parser.add_argument(
        "--ramp-stage-duration",
        type=int,
        default=DEFAULT_RAMP_STAGE_DURATION,
        dest="ramp_stage_duration",
        help=f"[ramp] Seconds to run each concurrency stage "
             f"(default: {DEFAULT_RAMP_STAGE_DURATION})",
    )
    # Shared args
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
        help=f"Minimum overall success-rate %% to exit 0 (default: {DEFAULT_FAIL_UNDER})",
    )
    return parser.parse_args()


def _parse_ramp_stages(raw: str) -> list[int]:
    """Parse a comma-separated concurrency string into a validated integer list."""

    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        raise ValueError("--ramp-stages must contain at least one concurrency value")
    values = []
    for part in parts:
        try:
            v = int(part)
        except ValueError:
            raise ValueError(f"--ramp-stages: '{part}' is not a valid integer") from None
        if v < 1:
            raise ValueError(f"--ramp-stages: each concurrency value must be >= 1, got {v}")
        values.append(v)
    return values


def main() -> int:
    args = _parse_args()

    if not args.api_key:
        print(
            "Error: --api-key or $AIS_API_KEY is required.\n"
            "Example: export AIS_API_KEY=your-key && python tests/load/run_load_test.py",
            file=sys.stderr,
        )
        return 1

    if args.mode == "burst":
        return _main_burst(args)
    else:
        return _main_ramp(args)


def _main_burst(args: argparse.Namespace) -> int:
    config = {
        "mode": "burst",
        "base_url": args.url,
        "auth_header": args.auth_header,
        "concurrency": args.concurrency,
        "total_requests": args.total_requests,
        "timeout_s": args.timeout,
        "fail_under_pct": args.fail_under,
        "payload_count": len(LOAD_PAYLOADS),
    }

    print(f"Starting burst: {config['total_requests']} requests, "
          f"{config['concurrency']} concurrent -> {args.url}{ASSESSMENT_ENDPOINT}")

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


def _main_ramp(args: argparse.Namespace) -> int:
    try:
        stage_concurrencies = _parse_ramp_stages(args.ramp_stages)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.ramp_stage_duration < 1:
        print("Error: --ramp-stage-duration must be >= 1", file=sys.stderr)
        return 1

    config = {
        "mode": "ramp",
        "base_url": args.url,
        "auth_header": args.auth_header,
        "ramp_stages": stage_concurrencies,
        "ramp_stage_duration_s": args.ramp_stage_duration,
        "timeout_s": args.timeout,
        "fail_under_pct": args.fail_under,
        "payload_count": len(LOAD_PAYLOADS),
    }

    total_duration = len(stage_concurrencies) * args.ramp_stage_duration
    print(
        f"Starting ramp: {len(stage_concurrencies)} stages "
        f"({', '.join(str(c) for c in stage_concurrencies)} concurrent), "
        f"{args.ramp_stage_duration}s each, "
        f"~{total_duration}s total -> {args.url}{ASSESSMENT_ENDPOINT}"
    )

    stage_bundles = asyncio.run(
        run_ramp(
            base_url=args.url,
            api_key=args.api_key,
            auth_header=args.auth_header,
            stage_concurrencies=stage_concurrencies,
            stage_duration_seconds=float(args.ramp_stage_duration),
            timeout_seconds=args.timeout,
        )
    )

    # Per-stage metrics
    stage_metrics = [compute_stage_metrics(bundle) for bundle in stage_bundles]

    # Aggregate metrics across all stages
    all_results = [r for bundle in stage_bundles for r in bundle["results"]]
    total_wall = sum(bundle["wall_elapsed_s"] for bundle in stage_bundles)
    aggregate = compute_metrics(all_results, total_wall)
    aggregate["scenario"] = "ramp-aggregate"

    print_summary(aggregate, config, stage_metrics=stage_metrics)
    write_report(aggregate, config, args.report, stage_metrics=stage_metrics)

    if aggregate["success_rate_pct"] < args.fail_under:
        print(
            f"  FAIL: overall success rate {aggregate['success_rate_pct']:.1f}% "
            f"is below --fail-under {args.fail_under:.1f}%",
            file=sys.stderr,
        )
        return 1

    print(f"  PASS: overall success rate {aggregate['success_rate_pct']:.1f}% "
          f">= --fail-under {args.fail_under:.1f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
