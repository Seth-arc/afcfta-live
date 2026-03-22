from __future__ import annotations

import asyncio
import csv
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from sqlalchemy import text

from app.db.base import get_async_session_factory


ROOT_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT_DIR / "data" / "staged" / "review_queue"
REVIEW_QUEUE_CSV_PATH = OUTPUT_DIR / "psr_review_queue.csv"
REVIEW_SUMMARY_PATH = OUTPUT_DIR / "psr_review_summary.txt"


@dataclass(frozen=True)
class ReviewRow:
    hs_code: str
    hs_level: str
    product_description: str
    legal_rule_text_verbatim: str
    component_type: str
    confidence_score: Decimal
    review_reason: str


def confidence_bucket(confidence_score: Decimal) -> str:
    if confidence_score == Decimal("1.000"):
        return "1.0"
    if Decimal("0.500") <= confidence_score < Decimal("1.000"):
        return "0.5-0.99"
    if Decimal("0.000") < confidence_score < Decimal("0.500"):
        return "0.01-0.49"
    return "0.0"


def review_reason(component_type: str, confidence_score: Decimal) -> str:
    if component_type == "NOTE":
        return "NOTE type"
    if component_type == "PROCESS":
        return "PROCESS type"
    if confidence_score == Decimal("0.000"):
        return "parse failure"
    return "low confidence"


async def fetch_review_rows() -> list[ReviewRow]:
    session_factory = get_async_session_factory()

    async with session_factory() as session:
        result = await session.execute(
            text(
                """
                SELECT
                    rule.hs_code,
                    rule.hs_level::text AS hs_level,
                    rule.product_description,
                    rule.legal_rule_text_verbatim,
                    component.component_type::text AS component_type,
                    component.confidence_score
                FROM psr_rule rule
                JOIN psr_rule_component component ON component.psr_id = rule.psr_id
                WHERE component.confidence_score < 1.000
                ORDER BY component.confidence_score ASC, component.component_type::text ASC, rule.hs_code ASC
                """
            )
        )
        rows = result.all()

    return [
        ReviewRow(
            hs_code=row.hs_code,
            hs_level=row.hs_level,
            product_description=row.product_description,
            legal_rule_text_verbatim=row.legal_rule_text_verbatim,
            component_type=row.component_type,
            confidence_score=Decimal(str(row.confidence_score)),
            review_reason=review_reason(row.component_type, Decimal(str(row.confidence_score))),
        )
        for row in rows
    ]


def write_review_csv(rows: list[ReviewRow]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with REVIEW_QUEUE_CSV_PATH.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "hs_code",
                "hs_level",
                "product_description",
                "legal_rule_text_verbatim",
                "component_type",
                "confidence_score",
                "review_reason",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "hs_code": row.hs_code,
                    "hs_level": row.hs_level,
                    "product_description": row.product_description,
                    "legal_rule_text_verbatim": row.legal_rule_text_verbatim,
                    "component_type": row.component_type,
                    "confidence_score": f"{row.confidence_score:.3f}",
                    "review_reason": row.review_reason,
                }
            )


def build_summary_text(rows: list[ReviewRow]) -> str:
    unique_rule_keys = {
        (row.hs_code, row.hs_level, row.product_description, row.legal_rule_text_verbatim)
        for row in rows
    }
    bucket_counts = Counter(confidence_bucket(row.confidence_score) for row in rows)
    component_type_counts = Counter(row.component_type for row in rows)
    reason_counts = Counter(row.review_reason for row in rows)

    lines = [
        "PSR review queue summary",
        f"Total low-confidence component rows: {len(rows)}",
        f"Total distinct rules needing review: {len(unique_rule_keys)}",
        "",
        "Counts by confidence bucket:",
        f"- 1.0: {bucket_counts.get('1.0', 0)}",
        f"- 0.5-0.99: {bucket_counts.get('0.5-0.99', 0)}",
        f"- 0.01-0.49: {bucket_counts.get('0.01-0.49', 0)}",
        f"- 0.0: {bucket_counts.get('0.0', 0)}",
        "",
        "Counts by component type:",
    ]

    for component_type, count in sorted(component_type_counts.items()):
        lines.append(f"- {component_type}: {count}")

    lines.extend([
        "",
        "Counts by review reason:",
    ])
    for reason, count in sorted(reason_counts.items()):
        lines.append(f"- {reason}: {count}")

    return "\n".join(lines) + "\n"


def write_summary(summary_text: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REVIEW_SUMMARY_PATH.write_text(summary_text, encoding="utf-8")


async def main() -> int:
    review_rows = await fetch_review_rows()
    write_review_csv(review_rows)
    summary_text = build_summary_text(review_rows)
    write_summary(summary_text)

    reason_counts = Counter(row.review_reason for row in review_rows)
    unique_rule_keys = {
        (row.hs_code, row.hs_level, row.product_description, row.legal_rule_text_verbatim)
        for row in review_rows
    }

    print(f"Review queue CSV: {REVIEW_QUEUE_CSV_PATH}")
    print(f"Review summary: {REVIEW_SUMMARY_PATH}")
    print(f"Total rules needing review: {len(unique_rule_keys)}")
    for reason, count in sorted(reason_counts.items()):
        print(f"- {reason}: {count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))