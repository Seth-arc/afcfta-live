"""Human-run verification harness for current-commit test and load artifacts.

The repository owner runs this script locally. It writes commit-scoped XML,
coverage, and load-test artifacts under `artifacts/verification/<git-sha>/`.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import socket
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACTS_ROOT = PROJECT_ROOT / "artifacts" / "verification"
DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_SMALL_LOAD_BASELINE = PROJECT_ROOT / "tests" / "load" / "baseline.json"
DEFAULT_LARGE_LOAD_BASELINE = PROJECT_ROOT / "tests" / "load" / "baseline_100c.json"
ASSISTANT_TEST_PATHS = (
    "tests/integration/test_assistant_api.py",
    "tests/integration/test_nim_full_flow.py",
)
IGNORED_GIT_STATUS_DIR_MARKERS = (
    "__pycache__/",
    ".hypothesis/",
    ".pytest_cache/",
    "artifacts/",
)
IGNORED_GIT_STATUS_SUFFIXES = (
    ".pyc",
    ".pyo",
    ".pyd",
)
IGNORED_GIT_STATUS_BASENAMES = (
    ".coverage",
)


@dataclass(slots=True)
class CommandResult:
    name: str
    command: list[str]
    returncode: int
    log_path: str
    junit_path: str | None = None
    coverage_data_path: str | None = None
    coverage_xml_path: str | None = None
    report_path: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run current-commit verification suites and publish artifacts.",
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Allow diagnostic runs from a dirty worktree. Do not use for release-gate publication.",
    )
    parser.add_argument(
        "--skip-unit",
        action="store_true",
        help="Skip the unit-test suite.",
    )
    parser.add_argument(
        "--skip-integration",
        action="store_true",
        help="Skip the full integration suite.",
    )
    parser.add_argument(
        "--skip-assistant",
        action="store_true",
        help="Skip the assistant/NIM integration suite.",
    )
    parser.add_argument(
        "--skip-load",
        action="store_true",
        help="Skip load tests and baseline comparisons.",
    )
    parser.add_argument(
        "--artifacts-root",
        default=str(DEFAULT_ARTIFACTS_ROOT),
        help="Root directory for generated verification artifacts.",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("AIS_BASE_URL", DEFAULT_BASE_URL),
        help="Base URL for load tests. The API must already be running.",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("AIS_API_KEY") or os.environ.get("API_AUTH_KEY", ""),
        help="API key for load tests. Defaults to AIS_API_KEY or API_AUTH_KEY.",
    )
    return parser.parse_args()


def _git_value(*args: str, fallback: str) -> str:
    try:
        value = subprocess.check_output(
            ["git", *args],
            cwd=PROJECT_ROOT,
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return fallback
    return value or fallback


def _git_sha() -> str:
    return _git_value("rev-parse", "--short", "HEAD", fallback="nogit")


def _normalize_git_status_path(path: str) -> str:
    """Normalize one porcelain path so generated-file filters are platform-stable."""

    return path.strip().strip('"').replace("\\", "/")


def _is_ignored_git_status_path(path: str) -> bool:
    """Return True when a dirty path is generated cache/junk that should not block the gate."""

    normalized_path = _normalize_git_status_path(path)
    if not normalized_path:
        return False

    if any(marker in normalized_path for marker in IGNORED_GIT_STATUS_DIR_MARKERS):
        return True

    basename = normalized_path.rsplit("/", 1)[-1]
    if basename in IGNORED_GIT_STATUS_BASENAMES:
        return True
    if basename.startswith(".coverage."):
        return True
    if any(normalized_path.endswith(suffix) for suffix in IGNORED_GIT_STATUS_SUFFIXES):
        return True
    return False


def _git_dirty_paths() -> list[str]:
    """Return dirty worktree paths after filtering generated cache artifacts."""

    try:
        output = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=PROJECT_ROOT,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return []

    dirty_paths: list[str] = []
    for line in output.splitlines():
        if not line:
            continue
        path = line[3:] if len(line) > 3 else line
        if _is_ignored_git_status_path(path):
            continue
        dirty_paths.append(_normalize_git_status_path(path))
    return dirty_paths


def _git_dirty() -> bool:
    return bool(_git_dirty_paths())


def _display_command(command: list[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(command)
    return shlex.join(command)


def _run_command(
    *,
    name: str,
    command: list[str],
    log_path: Path,
    env: dict[str, str] | None = None,
) -> CommandResult:
    print(f"[verify] {name} -> {log_path}", flush=True)
    completed_returncode = 1
    with log_path.open("w", encoding="utf-8") as log_file:
        log_file.write(f"$ {_display_command(command)}\n\n")
        process = subprocess.Popen(
            command,
            cwd=PROJECT_ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="", flush=True)
            log_file.write(line)
        completed_returncode = process.wait()
    return CommandResult(
        name=name,
        command=command,
        returncode=completed_returncode,
        log_path=str(log_path),
    )


def _write_preflight_result(
    *,
    name: str,
    artifact_dir: Path,
    lines: list[str],
    returncode: int,
) -> CommandResult:
    log_path = artifact_dir / f"{name}.log"
    print(f"[verify] {name} -> {log_path}", flush=True)
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for line in lines:
        print(line, flush=True)
    return CommandResult(
        name=name,
        command=[],
        returncode=returncode,
        log_path=str(log_path),
    )


def _database_preflight(artifact_dir: Path) -> CommandResult:
    try:
        from app.config import get_settings

        settings = get_settings()
    except Exception as exc:  # pragma: no cover - user environment specific
        return _write_preflight_result(
            name="database-preflight",
            artifact_dir=artifact_dir,
            lines=[
                "Database preflight failed: unable to load application settings.",
                f"Reason: {exc}",
                "Set DATABASE_URL and DATABASE_URL_SYNC in .env or the process environment before running integration or assistant suites.",
            ],
            returncode=2,
        )

    parsed = urlparse(settings.DATABASE_URL)
    host = parsed.hostname or "localhost"
    port = parsed.port or 5432
    database = parsed.path.lstrip("/") or "(unspecified)"
    lines = [
        f"Resolved DATABASE_URL host={host} port={port} database={database}.",
    ]

    try:
        with socket.create_connection((host, port), timeout=2):
            lines.append("Database TCP reachability check passed.")
            lines.append(
                "Schema migrations and seed data are not verified by this preflight."
            )
            return _write_preflight_result(
                name="database-preflight",
                artifact_dir=artifact_dir,
                lines=lines,
                returncode=0,
            )
    except OSError as exc:
        lines.extend(
            [
                "Database TCP reachability check failed.",
                f"Reason: {exc}",
                "Integration and assistant/NIM suites require a running PostgreSQL instance, current migrations, and seeded data.",
                "See README.md Quick Start: configure DATABASE_URL and DATABASE_URL_SYNC, apply migrations, then run python scripts/seed_data.py.",
            ]
        )
        return _write_preflight_result(
            name="database-preflight",
            artifact_dir=artifact_dir,
            lines=lines,
            returncode=2,
        )


def _pytest_result(
    *,
    name: str,
    test_targets: list[str],
    artifact_dir: Path,
    junit_name: str,
    coverage_name: str,
    coverage_data_name: str,
    cov_fail_under: int | None = None,
) -> CommandResult:
    junit_path = artifact_dir / junit_name
    coverage_xml_path = artifact_dir / coverage_name
    coverage_data_path = artifact_dir / coverage_data_name
    log_path = artifact_dir / f"{name}.log"
    env = os.environ.copy()
    env["COVERAGE_FILE"] = str(coverage_data_path)
    command = [
        sys.executable,
        "-m",
        "pytest",
        *test_targets,
        "-v",
        f"--junitxml={junit_path}",
        "--cov=app",
        "--cov-report=term-missing",
        f"--cov-report=xml:{coverage_xml_path}",
    ]
    if cov_fail_under is not None:
        command.append(f"--cov-fail-under={cov_fail_under}")
    result = _run_command(name=name, command=command, log_path=log_path, env=env)
    result.junit_path = str(junit_path)
    result.coverage_data_path = str(coverage_data_path)
    result.coverage_xml_path = str(coverage_xml_path)
    return result


def _combine_coverage(
    artifact_dir: Path,
    results: list[CommandResult],
) -> dict[str, str] | None:
    coverage_files = [result.coverage_data_path for result in results if result.coverage_data_path]
    if not coverage_files:
        return None

    env = os.environ.copy()
    env["COVERAGE_FILE"] = str(artifact_dir / ".coverage")
    combine_result = _run_command(
        name="coverage-combine",
        command=[sys.executable, "-m", "coverage", "combine", str(artifact_dir)],
        log_path=artifact_dir / "coverage-combine.log",
        env=env,
    )
    if combine_result.returncode != 0:
        return None

    report_result = _run_command(
        name="coverage-report",
        command=[sys.executable, "-m", "coverage", "report"],
        log_path=artifact_dir / "coverage-report.log",
        env=env,
    )
    xml_path = artifact_dir / "coverage-combined.xml"
    xml_result = _run_command(
        name="coverage-xml",
        command=[sys.executable, "-m", "coverage", "xml", "-o", str(xml_path)],
        log_path=artifact_dir / "coverage-xml.log",
        env=env,
    )
    html_dir = artifact_dir / "coverage-html"
    html_result = _run_command(
        name="coverage-html",
        command=[sys.executable, "-m", "coverage", "html", "-d", str(html_dir)],
        log_path=artifact_dir / "coverage-html.log",
        env=env,
    )
    if any(result.returncode != 0 for result in (report_result, xml_result, html_result)):
        return None

    return {
        "combined_data_path": str(artifact_dir / ".coverage"),
        "combined_xml_path": str(xml_path),
        "combined_html_dir": str(html_dir),
    }


def _load_results(
    *,
    name: str,
    artifact_dir: Path,
    base_url: str,
    api_key: str,
    concurrency: int,
    requests: int,
    baseline_path: Path,
    max_p95_latency_s: float | None = None,
) -> list[CommandResult]:
    report_path = artifact_dir / f"{name}.json"
    load_result = _run_command(
        name=name,
        command=[
            sys.executable,
            "tests/load/run_load_test.py",
            "--mode",
            "burst",
            "--url",
            base_url,
            "--api-key",
            api_key,
            "--concurrency",
            str(concurrency),
            "--requests",
            str(requests),
            "--report",
            str(report_path),
        ],
        log_path=artifact_dir / f"{name}.log",
    )
    load_result.report_path = str(report_path)

    tolerance = "25" if concurrency == 10 else "50"
    compare_result = _run_command(
        name=f"{name}-compare",
        command=[
            sys.executable,
            "tests/load/compare_reports.py",
            "--baseline",
            str(baseline_path),
            "--report",
            str(report_path),
            "--min-success-rate",
            "95",
            "--latency-tolerance-pct",
            tolerance,
            *(
                ["--max-p95-latency-s", str(max_p95_latency_s)]
                if max_p95_latency_s is not None
                else []
            ),
        ],
        log_path=artifact_dir / f"{name}-compare.log",
    )
    compare_result.report_path = str(report_path)
    return [load_result, compare_result]


def _load_warmup(
    *,
    artifact_dir: Path,
    base_url: str,
    api_key: str,
) -> CommandResult:
    report_path = artifact_dir / "load-report-warmup.json"
    warmup_result = _run_command(
        name="load-report-warmup",
        command=[
            sys.executable,
            "tests/load/run_load_test.py",
            "--mode",
            "burst",
            "--url",
            base_url,
            "--api-key",
            api_key,
            "--concurrency",
            "2",
            "--requests",
            "20",
            "--report",
            str(report_path),
        ],
        log_path=artifact_dir / "load-report-warmup.log",
    )
    warmup_result.report_path = str(report_path)
    return warmup_result


def _write_manifest(
    *,
    artifact_dir: Path,
    results: list[CommandResult],
    combined_coverage: dict[str, str] | None,
) -> Path:
    manifest = {
        "git_sha": _git_sha(),
        "git_dirty": _git_dirty(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "artifact_dir": str(artifact_dir),
        "results": [asdict(result) for result in results],
        "combined_coverage": combined_coverage,
    }
    manifest_path = artifact_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path


def main() -> int:
    args = parse_args()
    if _git_dirty() and not args.allow_dirty:
        print(
            "Refusing to run verification from a dirty worktree. Commit or stash changes first, "
            "or pass --allow-dirty for a diagnostic-only run that cannot start the freeze window.",
            file=sys.stderr,
        )
        return 2
    artifact_dir = Path(args.artifacts_root) / _git_sha()
    shutil.rmtree(artifact_dir, ignore_errors=True)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    results: list[CommandResult] = []

    if not args.skip_integration or not args.skip_assistant:
        db_preflight = _database_preflight(artifact_dir)
        results.append(db_preflight)
        if db_preflight.returncode != 0:
            manifest_path = _write_manifest(
                artifact_dir=artifact_dir,
                results=results,
                combined_coverage=None,
            )
            print(f"[verify] manifest: {manifest_path}")
            print("[verify] failed suites: database-preflight", file=sys.stderr)
            return db_preflight.returncode

    if not args.skip_unit:
        results.append(
            _pytest_result(
                name="unit-tests",
                test_targets=["tests/unit"],
                artifact_dir=artifact_dir,
                junit_name="unit-tests.xml",
                coverage_name="unit-coverage.xml",
                coverage_data_name=".coverage.unit",
            )
        )

    if not args.skip_integration:
        results.append(
            _pytest_result(
                name="integration-tests",
                test_targets=["tests/integration"],
                artifact_dir=artifact_dir,
                junit_name="integration-tests.xml",
                coverage_name="integration-coverage.xml",
                coverage_data_name=".coverage.integration",
            )
        )

    if not args.skip_assistant:
        results.append(
            _pytest_result(
                name="assistant-nim-tests",
                test_targets=list(ASSISTANT_TEST_PATHS),
                artifact_dir=artifact_dir,
                junit_name="assistant-nim-tests.xml",
                coverage_name="assistant-nim-coverage.xml",
                coverage_data_name=".coverage.assistant",
                cov_fail_under=0,
            )
        )

    if not args.skip_load:
        if not args.api_key:
            print(
                "Load tests require --api-key or AIS_API_KEY/API_AUTH_KEY to be set.",
                file=sys.stderr,
            )
            return 2
        results.append(
            _load_warmup(
                artifact_dir=artifact_dir,
                base_url=args.base_url,
                api_key=args.api_key,
            )
        )
        results.extend(
            _load_results(
                name="load-report-ci",
                artifact_dir=artifact_dir,
                base_url=args.base_url,
                api_key=args.api_key,
                concurrency=10,
                requests=50,
                baseline_path=DEFAULT_SMALL_LOAD_BASELINE,
            )
        )
        results.extend(
            _load_results(
                name="load-report-100",
                artifact_dir=artifact_dir,
                base_url=args.base_url,
                api_key=args.api_key,
                concurrency=100,
                requests=500,
                baseline_path=DEFAULT_LARGE_LOAD_BASELINE,
                max_p95_latency_s=0.5,
            )
        )

    combined_coverage = _combine_coverage(artifact_dir, results)
    manifest_path = _write_manifest(
        artifact_dir=artifact_dir,
        results=results,
        combined_coverage=combined_coverage,
    )
    print(f"[verify] manifest: {manifest_path}")

    failed = [result.name for result in results if result.returncode != 0]
    if failed:
        print(f"[verify] failed suites: {', '.join(failed)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
