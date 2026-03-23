from __future__ import annotations

import asyncio
import csv
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from sqlalchemy import text

from app.core.enums import HsLevelEnum, RuleComponentTypeEnum, RuleStatusEnum
from app.db.base import get_async_session_factory
from scripts.parsers.applicability_builder import validate_output_rows as validate_applicability_output_rows
from scripts.parsers.artifact_contracts import ArtifactValidationResult, ParserArtifactValidationError
from scripts.parsers.pathway_builder import validate_output_rows as validate_pathway_output_rows
from scripts.parsers.rule_decomposer import validate_output_rows as validate_decomposed_output_rows


VALID_RULE_STATUSES = tuple(member.value for member in RuleStatusEnum)
VALID_COMPONENT_TYPES = tuple(member.value for member in RuleComponentTypeEnum)
VALID_HS_LEVELS = tuple(member.value for member in HsLevelEnum)
ROOT_DIR = Path(__file__).resolve().parents[2]
DECOMPOSED_INPUT_PATH = ROOT_DIR / "data" / "staged" / "raw_csv" / "appendix_iv_decomposed.csv"
PATHWAYS_INPUT_PATH = ROOT_DIR / "data" / "processed" / "rules" / "appendix_iv_pathways.csv"
APPLICABILITY_INPUT_PATH = ROOT_DIR / "data" / "processed" / "rules" / "appendix_iv_applicability.csv"


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    detail: str


def format_status(passed: bool) -> str:
    return "PASS" if passed else "FAIL"


def sql_literal_list(values: tuple[str, ...]) -> str:
    quoted_values = ", ".join(f"'{value}'" for value in values)
    return f"({quoted_values})"


def read_rows(input_path: Path) -> list[dict[str, str]]:
    with input_path.open("r", newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


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


async def scalar(session, sql: str, params: dict[str, object] | None = None):
    return await session.scalar(text(sql), params or {})


async def fetch_one(session, sql: str, params: dict[str, object] | None = None):
    result = await session.execute(text(sql), params or {})
    return result.one()


async def fetch_all(session, sql: str, params: dict[str, object] | None = None):
    result = await session.execute(text(sql), params or {})
    return result.all()


async def run_checks() -> list[CheckResult]:
    session_factory = get_async_session_factory()
    results: list[CheckResult] = []
    valid_rule_statuses_sql = sql_literal_list(VALID_RULE_STATUSES)
    valid_component_types_sql = sql_literal_list(VALID_COMPONENT_TYPES)
    valid_hs_levels_sql = sql_literal_list(VALID_HS_LEVELS)

    async with session_factory() as session:
        psr_rule_count = int(await scalar(session, "SELECT COUNT(*) FROM psr_rule") or 0)
        component_count = int(await scalar(session, "SELECT COUNT(*) FROM psr_rule_component") or 0)
        pathway_count = int(await scalar(session, "SELECT COUNT(*) FROM eligibility_rule_pathway") or 0)
        applicability_count = int(await scalar(session, "SELECT COUNT(*) FROM hs6_psr_applicability") or 0)
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
                f"SELECT COUNT(*) FROM psr_rule WHERE rule_status::text NOT IN {valid_rule_statuses_sql}",
            )
            or 0
        )
        invalid_component_type_count = int(
            await scalar(
                session,
                f"SELECT COUNT(*) FROM psr_rule_component WHERE component_type::text NOT IN {valid_component_types_sql}",
            )
            or 0
        )
        invalid_hs_level_count = int(
            await scalar(
                session,
                f"SELECT COUNT(*) FROM psr_rule WHERE hs_level::text NOT IN {valid_hs_levels_sql}",
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
                FROM eligibility_rule_pathway
                WHERE expression_json IS NULL
                   OR expression_json->>'expression' IS NULL
                """,
            )
            or 0
        )
        valid_json_expression_count = int(
            await scalar(
                session,
                """
                SELECT COUNT(*)
                FROM eligibility_rule_pathway
                WHERE expression_json IS NOT NULL
                  AND expression_json->>'expression' IS NOT NULL
                """,
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
                GROUP BY rule.psr_id
            )
            SELECT
                COUNT(*) FILTER (WHERE min_confidence_score = 1.000) AS bucket_100,
                COUNT(*) FILTER (WHERE min_confidence_score >= 0.500 AND min_confidence_score < 1.000) AS bucket_050_099,
                COUNT(*) FILTER (WHERE min_confidence_score > 0.000 AND min_confidence_score < 0.500) AS bucket_001_049,
                COUNT(*) FILTER (WHERE min_confidence_score = 0.000) AS bucket_000
            FROM rule_confidence
            """,
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

        covered_hs6_count = int(await scalar(session, "SELECT COUNT(DISTINCT hs6_id) FROM hs6_psr_applicability") or 0)
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
                """,
            )
            or 0
        )
        heading_1806_count = int(
            await scalar(
                session,
                "SELECT COUNT(*) FROM psr_rule WHERE hs_code = '1806' AND hs_level::text = 'heading'",
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
                WHERE product.heading = '1806'
                """,
            )
            or 0
        )
        pending_rule_count = int(
            await scalar(session, "SELECT COUNT(*) FROM psr_rule WHERE rule_status::text = 'pending'") or 0
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
    results = parser_artifact_check_results(run_parser_artifact_checks())
    results.extend(await run_checks())
    pass_count = sum(1 for result in results if result.passed)
    fail_count = len(results) - pass_count

    print("PSR validation checks")
    for result in results:
        print(f"- {format_status(result.passed)}: {result.name} ({result.detail})")

    print("Validation summary")
    print(f"- PASS count: {pass_count}")
    print(f"- FAIL count: {fail_count}")
    print(f"- Total checks: {len(results)}")

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))