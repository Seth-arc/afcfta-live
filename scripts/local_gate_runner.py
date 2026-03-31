"""Local verification runner that starts the API before invoking the gate suite.

This helper exists for developer-hosted Windows runs where the shell sandbox can
block detached Python processes. It seeds deterministic fixture data, starts a
local Uvicorn server with explicit pool/worker settings, waits for readiness,
and then delegates to ``scripts/run_verification.py`` for the actual suite.
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8002
DEFAULT_API_KEY = "dev-local-key"
DEFAULT_WORKERS = 4
DEFAULT_DB_POOL_SIZE = 8
DEFAULT_DB_POOL_MAX_OVERFLOW = 8
DEFAULT_SERVER_STARTUP_TIMEOUT_SECONDS = 45


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed data, start the API locally, and run the verification suite.",
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--api-key", default=os.environ.get("API_AUTH_KEY", DEFAULT_API_KEY))
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--db-pool-size", type=int, default=DEFAULT_DB_POOL_SIZE)
    parser.add_argument(
        "--db-pool-max-overflow",
        type=int,
        default=DEFAULT_DB_POOL_MAX_OVERFLOW,
    )
    parser.add_argument(
        "--startup-timeout-seconds",
        type=int,
        default=DEFAULT_SERVER_STARTUP_TIMEOUT_SECONDS,
    )
    parser.add_argument("--skip-seed", action="store_true")
    parser.add_argument("--skip-unit", action="store_true")
    parser.add_argument("--skip-integration", action="store_true")
    parser.add_argument("--skip-assistant", action="store_true")
    parser.add_argument("--skip-load", action="store_true")
    return parser.parse_args()


def _run(command: list[str], *, env: dict[str, str], name: str) -> None:
    print(f"[local-gate] {name}: {' '.join(command)}", flush=True)
    completed = subprocess.run(command, cwd=PROJECT_ROOT, env=env, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"{name} failed with exit code {completed.returncode}")


def _build_base_env(args: argparse.Namespace) -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault(
        "DATABASE_URL",
        "postgresql+asyncpg://afcfta:afcfta_dev@localhost:5432/afcfta",
    )
    env.setdefault(
        "DATABASE_URL_SYNC",
        "postgresql://afcfta:afcfta_dev@localhost:5432/afcfta",
    )
    env["API_AUTH_KEY"] = args.api_key
    env["ENV"] = env.get("ENV", "development")
    env["RATE_LIMIT_ENABLED"] = "false"
    env["REDIS_URL"] = env.get("REDIS_URL", "redis://127.0.0.1:6379/0")
    env["UVICORN_WORKERS"] = str(args.workers)
    env["DB_POOL_SIZE"] = str(args.db_pool_size)
    env["DB_POOL_MAX_OVERFLOW"] = str(args.db_pool_max_overflow)
    env["CACHE_STATIC_LOOKUPS"] = env.get("CACHE_STATIC_LOOKUPS", "true")
    env["CACHE_STATUS_LOOKUPS"] = env.get("CACHE_STATUS_LOOKUPS", "true")
    env["LOG_LEVEL"] = env.get("LOG_LEVEL", "WARNING")
    env["LOG_REQUESTS_ENABLED"] = "false"
    return env


def _server_logs(port: int) -> tuple[Path, Path]:
    artifact_dir = PROJECT_ROOT / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    return (
        artifact_dir / f"uvicorn-{port}.stdout.log",
        artifact_dir / f"uvicorn-{port}.stderr.log",
    )


def _wait_for_ready(*, base_url: str, api_key: str, timeout_seconds: int) -> None:
    deadline = time.monotonic() + timeout_seconds
    headers = {"X-API-Key": api_key}
    request = Request(f"{base_url}/api/v1/health/ready", headers=headers)

    while time.monotonic() < deadline:
        try:
            with urlopen(request, timeout=3) as response:
                if response.status == 200:
                    return
        except HTTPError:
            pass
        except URLError:
            pass
        time.sleep(1)

    raise TimeoutError(
        f"API did not become ready within {timeout_seconds} seconds at {base_url}"
    )


def _terminate_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["cmd", "/c", "taskkill", "/PID", str(process.pid), "/T", "/F"],
            cwd=PROJECT_ROOT,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return

    process.send_signal(signal.SIGTERM)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


def main() -> int:
    args = parse_args()
    env = _build_base_env(args)
    base_url = f"http://{args.host}:{args.port}"
    stdout_log, stderr_log = _server_logs(args.port)
    stdout_log.unlink(missing_ok=True)
    stderr_log.unlink(missing_ok=True)

    if not args.skip_seed:
        _run([sys.executable, "scripts/seed_data.py"], env=env, name="seed-data")

    with stdout_log.open("w", encoding="utf-8") as stdout_handle, stderr_log.open(
        "w",
        encoding="utf-8",
    ) as stderr_handle:
        server = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                args.host,
                "--port",
                str(args.port),
                "--workers",
                str(args.workers),
            ],
            cwd=PROJECT_ROOT,
            env=env,
            stdout=stdout_handle,
            stderr=stderr_handle,
            text=True,
        )
        try:
            _wait_for_ready(
                base_url=base_url,
                api_key=args.api_key,
                timeout_seconds=args.startup_timeout_seconds,
            )
            print(f"[local-gate] ready: {base_url}", flush=True)

            command = [
                sys.executable,
                "scripts/run_verification.py",
                "--base-url",
                base_url,
                "--api-key",
                args.api_key,
            ]
            if args.skip_unit:
                command.append("--skip-unit")
            if args.skip_integration:
                command.append("--skip-integration")
            if args.skip_assistant:
                command.append("--skip-assistant")
            if args.skip_load:
                command.append("--skip-load")

            _run(command, env=env, name="run-verification")
        finally:
            _terminate_process_tree(server)

    print(f"[local-gate] server logs: {stdout_log} / {stderr_log}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
