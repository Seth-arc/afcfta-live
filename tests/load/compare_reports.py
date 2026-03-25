"""
Compare a new load-test report against a stored baseline.

Usage
-----
    python tests/load/compare_reports.py \\
        --baseline tests/load/baseline.json \\
        --report artifacts/load-report-ci.json \\
        --latency-tolerance-pct 25 \\
        --min-success-rate 95

Exit codes
----------
    0   All checks pass — no regression detected.
    1   One or more checks failed — regression detected.
    2   Usage error (missing or malformed input files).

No dependencies beyond the Python standard library.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _load(path: str) -> dict:
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        print(f"Error: file not found: {path}", file=sys.stderr)
        sys.exit(2)
    except json.JSONDecodeError as exc:
        print(f"Error: invalid JSON in {path}: {exc}", file=sys.stderr)
        sys.exit(2)


def _p95(report: dict, label: str) -> float:
    try:
        value = report["metrics"]["latency_s"]["p95"]
        if value is None:
            raise KeyError("null")
        return float(value)
    except (KeyError, TypeError) as exc:
        print(
            f"Error: metrics.latency_s.p95 missing or null in {label}: {exc}",
            file=sys.stderr,
        )
        sys.exit(2)


def _success_rate(report: dict, label: str) -> float:
    try:
        return float(report["metrics"]["success_rate_pct"])
    except (KeyError, TypeError) as exc:
        print(
            f"Error: metrics.success_rate_pct missing in {label}: {exc}",
            file=sys.stderr,
        )
        sys.exit(2)


def _hr(char: str = "-", width: int = 52) -> str:
    return char * width


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare a load-test report against a stored baseline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--baseline",
        required=True,
        help="Path to the committed baseline JSON file",
    )
    parser.add_argument(
        "--report",
        required=True,
        help="Path to the new load-test report JSON file",
    )
    parser.add_argument(
        "--latency-tolerance-pct",
        type=float,
        default=25.0,
        dest="latency_tolerance_pct",
        help="Max allowed p95 increase as %% of baseline (default: 25.0)",
    )
    parser.add_argument(
        "--min-success-rate",
        type=float,
        default=95.0,
        dest="min_success_rate",
        help="Minimum required success-rate %% (default: 95.0)",
    )
    args = parser.parse_args()

    baseline = _load(args.baseline)
    report = _load(args.report)

    baseline_p95 = _p95(baseline, args.baseline)
    report_p95 = _p95(report, args.report)
    baseline_sr = _success_rate(baseline, args.baseline)
    report_sr = _success_rate(report, args.report)

    p95_ceiling = baseline_p95 * (1.0 + args.latency_tolerance_pct / 100.0)
    p95_delta_pct = (
        (report_p95 - baseline_p95) / baseline_p95 * 100.0 if baseline_p95 > 0 else 0.0
    )

    p95_ok = report_p95 <= p95_ceiling
    sr_ok = report_sr >= args.min_success_rate
    passed = p95_ok and sr_ok

    print()
    print("Load Baseline Comparison")
    print(_hr("="))
    print(f"  Baseline : {args.baseline}")
    print(f"  Report   : {args.report}")
    print()
    print(f"  {'Metric':<22} {'Baseline':>10} {'Current':>10}   Status")
    print("  " + _hr())

    p95_sign = "+" if p95_delta_pct >= 0 else ""
    p95_note = (
        f"{p95_sign}{p95_delta_pct:.1f}% vs +{args.latency_tolerance_pct:.0f}% ceiling"
    )
    print(
        f"  {'p95 latency (s)':<22} {baseline_p95:>10.4f} {report_p95:>10.4f}"
        f"   {'PASS' if p95_ok else 'FAIL'}  ({p95_note})"
    )

    sr_note = f"min {args.min_success_rate:.1f}%"
    print(
        f"  {'success rate (%)':<22} {baseline_sr:>10.2f} {report_sr:>10.2f}"
        f"   {'PASS' if sr_ok else 'FAIL'}  ({sr_note})"
    )

    print()
    if passed:
        print("  PASS: no regression detected.")
        return 0

    print("  FAIL: regression detected — see details above.", file=sys.stderr)
    print(file=sys.stderr)
    print("  To update the baseline after a deliberate performance change:", file=sys.stderr)
    print(f"    cp <new-report.json> {args.baseline}", file=sys.stderr)
    print(
        "    git add tests/load/baseline.json && "
        "git commit -m 'chore: update load baseline'",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
