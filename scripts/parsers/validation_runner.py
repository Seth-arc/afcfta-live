from __future__ import annotations

import argparse
import asyncio
import csv
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import UUID

from sqlalchemy import text

from app.core.enums import HsLevelEnum, RuleComponentTypeEnum, RuleStatusEnum
from app.db.base import get_async_session_factory
try:
    from scripts.parsers.applicability_builder import validate_output_rows as validate_applicability_output_rows
    from scripts.parsers.artifact_contracts import (
        ArtifactValidationIssue,
        ArtifactValidationResult,
        ParserArtifactValidationError,
    )
    from scripts.parsers.pathway_builder import validate_output_rows as validate_pathway_output_rows
    from scripts.parsers.rule_decomposer import validate_output_rows as validate_decomposed_output_rows
except ModuleNotFoundError:
    from applicability_builder import validate_output_rows as validate_applicability_output_rows
    from artifact_contracts import (
        ArtifactValidationIssue,
        ArtifactValidationResult,
        ParserArtifactValidationError,
    )
    from pathway_builder import validate_output_rows as validate_pathway_output_rows
    from rule_decomposer import validate_output_rows as validate_decomposed_output_rows


VALID_RULE_STATUSES = tuple(member.value for member in RuleStatusEnum)
VALID_COMPONENT_TYPES = tuple(member.value for member in RuleComponentTypeEnum)
VALID_HS_LEVELS = tuple(member.value for member in HsLevelEnum)
MANUAL_REVIEW_COMPONENT_TYPES = (
    RuleComponentTypeEnum.PROCESS.value,
    RuleComponentTypeEnum.NOTE.value,
)
MANUAL_REVIEW_CONFIDENCE = {
    RuleComponentTypeEnum.PROCESS.value: Decimal("0.500"),
    RuleComponentTypeEnum.NOTE.value: Decimal("0.000"),
}
EXECUTABLE_COMPONENT_CONFIDENCE = Decimal("1.000")
SOURCE_ID = UUID("a0000000-0000-0000-0000-000000000001")
ROOT_DIR = Path(__file__).resolve().parents[2]
DECOMPOSED_INPUT_PATH = ROOT_DIR / "data" / "staged" / "raw_csv" / "appendix_iv_decomposed.csv"
PATHWAYS_INPUT_PATH = ROOT_DIR / "data" / "processed" / "rules" / "appendix_iv_pathways.csv"
APPLICABILITY_INPUT_PATH = ROOT_DIR / "data" / "processed" / "rules" / "appendix_iv_applicability.csv"


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    detail: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate staged parser artifacts and/or promoted PSR database state."
    )
    parser.add_argument(
        "--scope",
        choices=("artifacts", "db", "all"),
        default="all",
        help="Which validation scope to run.",
    )
    parser.add_argument(
        "--all-sources",
        action="store_true",
        help="When running DB validation, check all PSR sources instead of only Appendix IV.",
    )
    return parser.parse_args()


def format_status(passed: bool) -> str:
    return "PASS" if passed else "FAIL"


def sql_literal_list(values: tuple[str, ...]) -> str:
    quoted_values = ", ".join(f"'{value}'" for value in values)
    return f"({quoted_values})"


def read_rows(input_path: Path) -> list[dict[str, str]]:
    with input_path.open("r", newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def validate_parser_confidence_rows(
    decomposed_rows: list[dict[str, str]],
) -> ArtifactValidationResult:
    """Fail promotion when low-confidence parser output leaks beyond manual-review rows."""

    issues: list[ArtifactValidationIssue] = []

    for row_number, row in enumerate(decomposed_rows, start=1):
        component_type = str(row.get("component_type") or "").strip()
        confidence_raw = str(row.get("confidence_score") or "").strip()
        if not component_type or not confidence_raw:
            continue

        try:
            confidence_score = Decimal(confidence_raw)
        except InvalidOperation:
            # The decomposed contract validator reports malformed confidence values.
            continue

        row_key = "|".join(
            [
                str(row.get("hs_code") or "").strip(),
                str(row.get("component_type") or "").strip(),
                str(row.get("raw_rule_text") or "").strip(),
            ]
        )

        expected_manual_confidence = MANUAL_REVIEW_CONFIDENCE.get(component_type)
        if expected_manual_confidence is not None:
            if confidence_score != expected_manual_confidence:
                issues.append(
                    ArtifactValidationIssue(
                        artifact_type="parser confidence gate",
                        row_number=row_number,
                        field="confidence_score",
                        message=(
                            f"{component_type} rows must keep confidence_score "
                            f"{expected_manual_confidence:.3f} so manual-review inventory "
                            "stays isolated and auditable"
                        ),
                        row_key=row_key,
                        value=confidence_raw,
                    )
                )
            continue

        if confidence_score != EXECUTABLE_COMPONENT_CONFIDENCE:
            issues.append(
                ArtifactValidationIssue(
                    artifact_type="parser confidence gate",
                    row_number=row_number,
                    field="confidence_score",
                    message=(
                        "Executable parser rows must promote at confidence_score 1.000; "
                        "sub-1.0 confidence is only allowed for PROCESS/NOTE manual-review rows"
                    ),
                    row_key=row_key,
                    value=confidence_raw,
                )
            )

    return ArtifactValidationResult(
        artifact_type="parser confidence gate",
        total_rows=len(decomposed_rows),
        issues=tuple(issues),
    )


def run_parser_artifact_checks(
    decomposed_rows: list[dict[str, str]] | None = None,
    pathway_rows: list[dict[str, str]] | None = None,
    applicability_rows: list[dict[str, str]] | None = None,
) -> list[ArtifactValidationResult]:
    if decomposed_rows is None:
        if not DECOMPOSED_INPUT_PATH.exists():
            raise FileNotFoundError(f"Required input CSV not found: {DECOMPOSED_INPUT_PATH}")
        decomposed_rows = read_rows(DECOMPOSED_INPUT_PATH)
    if pathway_rows is None:
        if not PATHWAYS_INPUT_PATH.exists():
            raise FileNotFoundError(f"Required input CSV not found: {PATHWAYS_INPUT_PATH}")
        pathway_rows = read_rows(PATHWAYS_INPUT_PATH)
    if applicability_rows is None:
        if not APPLICABILITY_INPUT_PATH.exists():
            raise FileNotFoundError(f"Required input CSV not found: {APPLICABILITY_INPUT_PATH}")
        applicability_rows = read_rows(APPLICABILITY_INPUT_PATH)

    return [
        validate_decomposed_output_rows(decomposed_rows),
        validate_parser_confidence_rows(decomposed_rows),
        validate_pathway_output_rows(pathway_rows),
        validate_applicability_output_rows(applicability_rows),
    ]


def parser_artifact_check_results(results: list[ArtifactValidationResult]) -> list[CheckResult]:
    check_results: list[CheckResult] = []
    for result in results:
        detail = f"rows={result.total_rows}, invalid_rows={result.invalid_rows}, issues={len(result.issues)}"
        if result.issues:
            detail = f"{detail}, sample={result.issues[0].render()}"
        check_results.append(
            CheckResult(
                name=f"{result.artifact_type} contract validation",
                passed=result.passed,
                detail=detail,
            )
        )
    return check_results


def enforce_parser_artifact_contracts(
    decomposed_rows: list[dict[str, str]] | None = None,
    pathway_rows: list[dict[str, str]] | None = None,
    applicability_rows: list[dict[str, str]] | None = None,
) -> list[ArtifactValidationResult]:
    results = run_parser_artifact_checks(
        decomposed_rows=decomposed_rows,
        pathway_rows=pathway_rows,
        applicability_rows=applicability_rows,
    )
    failed_results = [result for result in results if not result.passed]
    if failed_results:
        raise ParserArtifactValidationError(failed_results)
    return results


def print_check_results(title: str, results: list[CheckResult]) -> None:
    print(title)
    for result in results:
        print(f"- {format_status(result.passed)}: {result.name} ({result.detail})")


def build_validation_summary(results: list[CheckResult]) -> tuple[int, int, int]:
    pass_count = sum(1 for result in results if result.passed)
    fail_count = len(results) - pass_count
    return pass_count, fail_count, len(results)


async def scalar(session, sql: str, params: dict[str, object] | None = None):
    return await session.scalar(text(sql), params or {})


async def fetch_one(session, sql: str, params: dict[str, object] | None = None):
    result = await session.execute(text(sql), params or {})
    return result.one()


async def fetch_all(session, sql: str, params: dict[str, object] | None = None):
    result = await session.execute(text(sql), params or {})
    return result.all()


def _db_scope_clause(alias: str, *, include_all_sources: bool) -> str:
    if include_all_sources:
        return ""
    return f"WHERE {alias}.source_id = :source_id"


def _db_scope_rule_join(
    child_alias: str,
    rule_alias: str,
    *,
    include_all_sources: bool,
) -> str:
    if include_all_sources:
        return ""
    return f" AND {rule_alias}.source_id = :source_id"


def _db_scope_params(*, include_all_sources: bool) -> dict[str, object]:
    return {} if include_all_sources else {"source_id": SOURCE_ID}


async def run_checks(*, include_all_sources: bool = False) -> list[CheckResult]:
    session_factory = get_async_session_factory()
    results: list[CheckResult] = []
    valid_rule_statuses_sql = sql_literal_list(VALID_RULE_STATUSES)
    valid_component_types_sql = sql_literal_list(VALID_COMPONENT_TYPES)
    valid_hs_levels_sql = sql_literal_list(VALID_HS_LEVELS)
    scope_params = _db_scope_params(include_all_sources=include_all_sources)
    rule_scope_clause = _db_scope_clause("rule", include_all_sources=include_all_sources)
    component_rule_scope = _db_scope_rule_join("component", "rule", include_all_sources=include_all_sources)
    pathway_rule_scope = _db_scope_rule_join("pathway", "rule", include_all_sources=include_all_sources)
    applicability_rule_scope = _db_scope_rule_join(
        "applicability",
        "rule",
        include_all_sources=include_all_sources,
    )

    async with session_factory() as session:
        psr_rule_count = int(
            await scalar(session, f"SELECT COUNT(*) FROM psr_rule rule {rule_scope_clause}", scope_params) or 0
        )
        component_count = int(
            await scalar(
                session,
                f"""
                SELECT COUNT(*)
                FROM psr_rule_component component
                JOIN psr_rule rule ON rule.psr_id = component.psr_id{component_rule_scope}
                """,
                scope_params,
            )
            or 0
        )
        pathway_count = int(
            await scalar(
                session,
                f"""
                SELECT COUNT(*)
                FROM eligibility_rule_pathway pathway
                JOIN psr_rule rule ON rule.psr_id = pathway.psr_id{pathway_rule_scope}
                """,
                scope_params,
            )
            or 0
        )
        applicability_count = int(
            await scalar(
                session,
                f"""
                SELECT COUNT(*)
                FROM hs6_psr_applicability applicability
                JOIN psr_rule rule ON rule.psr_id = applicability.psr_id{applicability_rule_scope}
                """,
                scope_params,
            )
            or 0
        )
        hs6_count = int(await scalar(session, "SELECT COUNT(*) FROM hs6_product") or 0)

        results.append(CheckResult("psr_rule row count > 100", psr_rule_count > 100, f"count={psr_rule_count}"))
        results.append(CheckResult("psr_rule_component count >= psr_rule count", component_count >= psr_rule_count, f"components={component_count}, rules={psr_rule_count}"))
        results.append(CheckResult("eligibility_rule_pathway count >= psr_rule count", pathway_count >= psr_rule_count, f"pathways={pathway_count}, rules={psr_rule_count}"))
        results.append(CheckResult("hs6_psr_applicability row count > 1000", applicability_count > 1000, f"count={applicability_count}"))

        orphan_component_count = int(
            await scalar(
                session,
                """
                SELECT COUNT(*)
                FROM psr_rule_component component
                LEFT JOIN psr_rule rule ON rule.psr_id = component.psr_id
                WHERE rule.psr_id IS NULL
                """,
            )
            or 0
        )
        orphan_pathway_count = int(
            await scalar(
                session,
                """
                SELECT COUNT(*)
                FROM eligibility_rule_pathway pathway
                LEFT JOIN psr_rule rule ON rule.psr_id = pathway.psr_id
                WHERE rule.psr_id IS NULL
                """,
            )
            or 0
        )
        orphan_applicability_psr_count = int(
            await scalar(
                session,
                """
                SELECT COUNT(*)
                FROM hs6_psr_applicability applicability
                LEFT JOIN psr_rule rule ON rule.psr_id = applicability.psr_id
                WHERE rule.psr_id IS NULL
                """,
            )
            or 0
        )
        orphan_applicability_hs6_count = int(
            await scalar(
                session,
                """
                SELECT COUNT(*)
                FROM hs6_psr_applicability applicability
                LEFT JOIN hs6_product product ON product.hs6_id = applicability.hs6_id
                WHERE product.hs6_id IS NULL
                """,
            )
            or 0
        )

        results.append(CheckResult("All psr_rule_component.psr_id values resolve", orphan_component_count == 0, f"orphans={orphan_component_count}"))
        results.append(CheckResult("All eligibility_rule_pathway.psr_id values resolve", orphan_pathway_count == 0, f"orphans={orphan_pathway_count}"))
        results.append(CheckResult("All hs6_psr_applicability.psr_id values resolve", orphan_applicability_psr_count == 0, f"orphans={orphan_applicability_psr_count}"))
        results.append(CheckResult("All hs6_psr_applicability.hs6_id values resolve", orphan_applicability_hs6_count == 0, f"orphans={orphan_applicability_hs6_count}"))

        invalid_rule_status_count = int(
            await scalar(
                session,
                f"SELECT COUNT(*) FROM psr_rule rule {rule_scope_clause} AND rule.rule_status::text NOT IN {valid_rule_statuses_sql}" if rule_scope_clause else f"SELECT COUNT(*) FROM psr_rule rule WHERE rule.rule_status::text NOT IN {valid_rule_statuses_sql}",
                scope_params,
            )
            or 0
        )
        invalid_component_type_count = int(
            await scalar(
                session,
                f"""
                SELECT COUNT(*)
                FROM psr_rule_component component
                JOIN psr_rule rule ON rule.psr_id = component.psr_id{component_rule_scope}
                WHERE component.component_type::text NOT IN {valid_component_types_sql}
                """,
                scope_params,
            )
            or 0
        )
        invalid_hs_level_count = int(
            await scalar(
                session,
                f"SELECT COUNT(*) FROM psr_rule rule {rule_scope_clause} AND rule.hs_level::text NOT IN {valid_hs_levels_sql}" if rule_scope_clause else f"SELECT COUNT(*) FROM psr_rule rule WHERE rule.hs_level::text NOT IN {valid_hs_levels_sql}",
                scope_params,
            )
            or 0
        )

        results.append(CheckResult("All psr_rule.rule_status values are valid", invalid_rule_status_count == 0, f"invalid={invalid_rule_status_count}"))
        results.append(CheckResult("All psr_rule_component.component_type values are valid", invalid_component_type_count == 0, f"invalid={invalid_component_type_count}"))
        results.append(CheckResult("All psr_rule.hs_level values are valid", invalid_hs_level_count == 0, f"invalid={invalid_hs_level_count}"))

        null_expression_count = int(
            await scalar(
                session,
                """
                SELECT COUNT(*)
                FROM eligibility_rule_pathway pathway
                JOIN psr_rule rule ON rule.psr_id = pathway.psr_id
                WHERE expression_json IS NULL
                   OR expression_json->>'expression' IS NULL
                """ + ("" if include_all_sources else " AND rule.source_id = :source_id"),
                scope_params,
            )
            or 0
        )
        valid_json_expression_count = int(
            await scalar(
                session,
                """
                SELECT COUNT(*)
                FROM eligibility_rule_pathway pathway
                JOIN psr_rule rule ON rule.psr_id = pathway.psr_id
                WHERE expression_json IS NOT NULL
                  AND expression_json->>'expression' IS NOT NULL
                """ + ("" if include_all_sources else " AND rule.source_id = :source_id"),
                scope_params,
            )
            or 0
        )

        results.append(CheckResult("Null expression_json count captured", True, f"null_expression_json={null_expression_count}"))
        results.append(CheckResult("Valid JSON expression_json count captured", True, f"valid_expression_json={valid_json_expression_count}"))

        confidence_rows = await fetch_all(
            session,
            """
            WITH rule_confidence AS (
                SELECT
                    rule.psr_id,
                    MIN(component.confidence_score) AS min_confidence_score
                FROM psr_rule rule
                JOIN psr_rule_component component ON component.psr_id = rule.psr_id
                {scope_clause}
                GROUP BY rule.psr_id
            )
            SELECT
                COUNT(*) FILTER (WHERE min_confidence_score = 1.000) AS bucket_100,
                COUNT(*) FILTER (WHERE min_confidence_score >= 0.500 AND min_confidence_score < 1.000) AS bucket_050_099,
                COUNT(*) FILTER (WHERE min_confidence_score > 0.000 AND min_confidence_score < 0.500) AS bucket_001_049,
                COUNT(*) FILTER (WHERE min_confidence_score = 0.000) AS bucket_000
            FROM rule_confidence
            """.format(scope_clause=rule_scope_clause),
            scope_params,
        )
        bucket_100, bucket_050_099, bucket_001_049, bucket_000 = confidence_rows[0]
        confidence_total = int(bucket_100 or 0) + int(bucket_050_099 or 0) + int(bucket_001_049 or 0) + int(bucket_000 or 0)
        results.append(
            CheckResult(
                "Rule confidence distribution captured",
                confidence_total == psr_rule_count,
                (
                    f"1.0={int(bucket_100 or 0)}, "
                    f"0.5-0.99={int(bucket_050_099 or 0)}, "
                    f"0.01-0.49={int(bucket_001_049 or 0)}, "
                    f"0.0={int(bucket_000 or 0)}"
                ),
            )
        )
        low_confidence_executable_count = int(
            await scalar(
                session,
                f"""
                SELECT COUNT(*)
                FROM psr_rule_component component
                JOIN psr_rule rule ON rule.psr_id = component.psr_id{component_rule_scope}
                WHERE component.component_type::text NOT IN {sql_literal_list(MANUAL_REVIEW_COMPONENT_TYPES)}
                  AND component.confidence_score < {EXECUTABLE_COMPONENT_CONFIDENCE}
                """,
                scope_params,
            )
            or 0
        )
        invalid_process_confidence_count = int(
            await scalar(
                session,
                f"""
                SELECT COUNT(*)
                FROM psr_rule_component component
                JOIN psr_rule rule ON rule.psr_id = component.psr_id{component_rule_scope}
                WHERE component.component_type::text = '{RuleComponentTypeEnum.PROCESS.value}'
                  AND component.confidence_score <> {MANUAL_REVIEW_CONFIDENCE[RuleComponentTypeEnum.PROCESS.value]}
                """,
                scope_params,
            )
            or 0
        )
        invalid_note_confidence_count = int(
            await scalar(
                session,
                f"""
                SELECT COUNT(*)
                FROM psr_rule_component component
                JOIN psr_rule rule ON rule.psr_id = component.psr_id{component_rule_scope}
                WHERE component.component_type::text = '{RuleComponentTypeEnum.NOTE.value}'
                  AND component.confidence_score <> {MANUAL_REVIEW_CONFIDENCE[RuleComponentTypeEnum.NOTE.value]}
                """,
                scope_params,
            )
            or 0
        )
        review_queue_rows = await fetch_all(
            session,
            f"""
            SELECT
                component.component_type::text AS component_type,
                COUNT(*) AS row_count
            FROM psr_rule_component component
            JOIN psr_rule rule ON rule.psr_id = component.psr_id{component_rule_scope}
            WHERE component.component_type::text IN {sql_literal_list(MANUAL_REVIEW_COMPONENT_TYPES)}
              AND component.confidence_score < {EXECUTABLE_COMPONENT_CONFIDENCE}
            GROUP BY component.component_type::text
            ORDER BY component.component_type::text ASC
            """,
            scope_params,
        )
        review_queue_detail = ", ".join(
            f"{component_type}={int(row_count)}" for component_type, row_count in review_queue_rows
        ) or "none"
        results.append(
            CheckResult(
                "Executable parser components are fully confident",
                low_confidence_executable_count == 0,
                f"invalid={low_confidence_executable_count}",
            )
        )
        results.append(
            CheckResult(
                "PROCESS manual-review rows stay pinned at 0.500 confidence",
                invalid_process_confidence_count == 0,
                f"invalid={invalid_process_confidence_count}",
            )
        )
        results.append(
            CheckResult(
                "NOTE manual-review rows stay pinned at 0.000 confidence",
                invalid_note_confidence_count == 0,
                f"invalid={invalid_note_confidence_count}",
            )
        )
        results.append(
            CheckResult(
                "Manual-review parser inventory isolated to PROCESS/NOTE rows",
                True,
                review_queue_detail,
            )
        )

        covered_hs6_count = int(
            await scalar(
                session,
                f"""
                SELECT COUNT(DISTINCT applicability.hs6_id)
                FROM hs6_psr_applicability applicability
                JOIN psr_rule rule ON rule.psr_id = applicability.psr_id{applicability_rule_scope}
                """,
                scope_params,
            )
            or 0
        )
        coverage_percent = Decimal("0.00")
        if hs6_count > 0:
            coverage_percent = (Decimal(covered_hs6_count) / Decimal(hs6_count)) * Decimal("100")
        results.append(
            CheckResult(
                "HS6 applicability coverage calculated",
                hs6_count > 0,
                f"covered={covered_hs6_count}, total={hs6_count}, coverage={coverage_percent.quantize(Decimal('0.01'))}%",
            )
        )

        chapter_01_wo_count = int(
            await scalar(
                session,
                """
                SELECT COUNT(*)
                FROM psr_rule rule
                JOIN psr_rule_component component ON component.psr_id = rule.psr_id
                WHERE rule.hs_code = '01'
                  AND rule.hs_level::text = 'chapter'
                  AND component.component_type::text = 'WO'
                """ + ("" if include_all_sources else " AND rule.source_id = :source_id"),
                scope_params,
            )
            or 0
        )
        heading_1806_count = int(
            await scalar(
                session,
                "SELECT COUNT(*) FROM psr_rule rule WHERE rule.hs_code = '1806' AND rule.hs_level::text = 'heading'"
                + ("" if include_all_sources else " AND rule.source_id = :source_id"),
                scope_params,
            )
            or 0
        )
        heading_1806_coverage_count = int(
            await scalar(
                session,
                """
                SELECT COUNT(DISTINCT product.hs6_id)
                FROM hs6_product product
                JOIN hs6_psr_applicability applicability ON applicability.hs6_id = product.hs6_id
                JOIN psr_rule rule ON rule.psr_id = applicability.psr_id
                WHERE product.heading = '1806'
                """ + ("" if include_all_sources else " AND rule.source_id = :source_id"),
                scope_params,
            )
            or 0
        )
        pending_rule_count = int(
            await scalar(
                session,
                "SELECT COUNT(*) FROM psr_rule rule WHERE rule.rule_status::text = 'pending'"
                + ("" if include_all_sources else " AND rule.source_id = :source_id"),
                scope_params,
            )
            or 0
        )

        results.append(CheckResult("Chapter 01 has a WO rule", chapter_01_wo_count > 0, f"matches={chapter_01_wo_count}"))
        results.append(
            CheckResult(
                "Heading 1806 exists or is covered",
                heading_1806_count > 0 or heading_1806_coverage_count > 0,
                f"direct_rules={heading_1806_count}, covered_hs6={heading_1806_coverage_count}",
            )
        )
        results.append(CheckResult("At least one pending rule exists", pending_rule_count > 0, f"matches={pending_rule_count}"))

    return results


async def main() -> int:
    args = parse_args()
    all_results: list[CheckResult] = []

    if args.scope in {"artifacts", "all"}:
        artifact_results = parser_artifact_check_results(run_parser_artifact_checks())
        print_check_results("Parser artifact validation", artifact_results)
        all_results.extend(artifact_results)

    if args.scope in {"db", "all"}:
        db_results = await run_checks(include_all_sources=args.all_sources)
        print_check_results("PSR database validation", db_results)
        all_results.extend(db_results)

    pass_count, fail_count, total_count = build_validation_summary(all_results)
    print("Validation summary")
    print(f"- PASS count: {pass_count}")
    print(f"- FAIL count: {fail_count}")
    print(f"- Total checks: {total_count}")

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
