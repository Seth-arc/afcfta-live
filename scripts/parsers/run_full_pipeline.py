from __future__ import annotations

import argparse
import csv
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import text

from app.db.base import get_async_session_factory


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT_DIR / "scripts" / "parsers"


@dataclass(frozen=True)
class PipelineStep:
    index: int
    name: str
    script_name: str
    expected_outputs: tuple[Path, ...] = ()
    requires_insert: bool = False


STEPS = (
    PipelineStep(1, "Appendix IV extractor", "appendix_iv_extractor.py", (ROOT_DIR / "data" / "staged" / "extracted_tables" / "appendix_iv_raw.csv",)),
    PipelineStep(2, "PSR row classifier", "psr_row_classifier.py", (ROOT_DIR / "data" / "staged" / "raw_csv" / "appendix_iv_classified.csv",)),
    PipelineStep(3, "HS code normalizer", "hs_code_normalizer.py", (ROOT_DIR / "data" / "staged" / "raw_csv" / "appendix_iv_hs_normalized.csv",)),
    PipelineStep(4, "Rule decomposer", "rule_decomposer.py", (ROOT_DIR / "data" / "staged" / "raw_csv" / "appendix_iv_decomposed.csv",)),
    PipelineStep(5, "Pathway builder", "pathway_builder.py", (ROOT_DIR / "data" / "processed" / "rules" / "appendix_iv_pathways.csv",)),
    PipelineStep(6, "Applicability builder", "applicability_builder.py", (ROOT_DIR / "data" / "processed" / "rules" / "appendix_iv_applicability.csv",)),
    PipelineStep(7, "PSR DB inserter", "psr_db_inserter.py"),
    PipelineStep(8, "Validation runner", "validation_runner.py", requires_insert=True),
    PipelineStep(9, "Review queue exporter", "review_queue_exporter.py", (ROOT_DIR / "data" / "staged" / "review_queue" / "psr_review_queue.csv", ROOT_DIR / "data" / "staged" / "review_queue" / "psr_review_summary.txt"), requires_insert=True),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the full Appendix IV parser pipeline.")
    parser.add_argument("--start-from", type=int, default=1, help="Step number to start from.")
    parser.add_argument("--skip-insert", action="store_true", help="Skip database insertion and DB-dependent validation/review steps.")
    return parser.parse_args()


def count_csv_rows(csv_path: Path) -> int:
    if not csv_path.exists() or csv_path.suffix.lower() != ".csv":
        return 0
    with csv_path.open("r", newline="", encoding="utf-8") as csv_file:
        reader = csv.reader(csv_file)
        next(reader, None)
        return sum(1 for _ in reader)


async def fetch_db_counts() -> dict[str, int]:
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        queries = {
            "psr_rule": "SELECT COUNT(*) FROM psr_rule",
            "psr_rule_component": "SELECT COUNT(*) FROM psr_rule_component",
            "eligibility_rule_pathway": "SELECT COUNT(*) FROM eligibility_rule_pathway",
            "hs6_psr_applicability": "SELECT COUNT(*) FROM hs6_psr_applicability",
        }
        counts: dict[str, int] = {}
        for label, sql in queries.items():
            counts[label] = int(await session.scalar(text(sql)) or 0)
        return counts


def ensure_outputs_exist(step: PipelineStep) -> None:
    missing_outputs = [str(path) for path in step.expected_outputs if not path.exists()]
    if missing_outputs:
        raise FileNotFoundError(
            f"Step {step.index} ({step.name}) completed but expected outputs were missing: {', '.join(missing_outputs)}"
        )


def run_step(step: PipelineStep) -> float:
    script_path = SCRIPTS_DIR / step.script_name
    if not script_path.exists():
        raise FileNotFoundError(f"Step script not found: {script_path}")

    print(f"\n=== Step {step.index}: {step.name} ===")
    start_time = time.perf_counter()
    result = subprocess.run([sys.executable, str(script_path)], cwd=str(ROOT_DIR), check=False)
    elapsed = time.perf_counter() - start_time

    if result.returncode != 0:
        raise RuntimeError(f"Step {step.index} failed with exit code {result.returncode}: {step.script_name}")

    ensure_outputs_exist(step)
    return elapsed


def main() -> int:
    args = parse_args()
    if args.start_from < 1 or args.start_from > len(STEPS):
        raise ValueError(f"--start-from must be between 1 and {len(STEPS)}")

    executed_steps: list[tuple[PipelineStep, float]] = []
    total_start = time.perf_counter()

    for step in STEPS:
        if step.index < args.start_from:
            continue
        if args.skip_insert and step.index >= 7:
            print(f"\n=== Skipping Step {step.index}: {step.name} (--skip-insert) ===")
            continue

        try:
            elapsed = run_step(step)
        except Exception as exc:
            print(f"Pipeline stopped at step {step.index} ({step.name}): {exc}")
            return 1
        executed_steps.append((step, elapsed))

    total_elapsed = time.perf_counter() - total_start

    print("\nPipeline summary")
    print(f"- Total elapsed: {total_elapsed:.2f}s")
    for step, elapsed in executed_steps:
        print(f"- Step {step.index} {step.name}: {elapsed:.2f}s")

    print("Row counts")
    for step in STEPS:
        for output_path in step.expected_outputs:
            if output_path.suffix.lower() == ".csv" and output_path.exists():
                print(f"- {output_path.name}: {count_csv_rows(output_path)} rows")

    if not args.skip_insert and any(step.index >= 7 for step, _ in executed_steps):
        try:
            import asyncio

            db_counts = asyncio.run(fetch_db_counts())
            for label, count in db_counts.items():
                print(f"- {label}: {count} rows")
        except Exception as exc:
            print(f"- Database row count summary unavailable: {exc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())