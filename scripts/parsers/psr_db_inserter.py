from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
from collections import OrderedDict
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from app.core.enums import HsLevelEnum, OperatorTypeEnum, RuleComponentTypeEnum, RuleStatusEnum, ThresholdBasisEnum
from app.db.base import get_async_session_factory
from app.db.models.rules import EligibilityRulePathway, HS6PSRApplicability, PSRRule, PSRRuleComponent
try:
    from scripts.parsers.validation_runner import enforce_parser_artifact_contracts, format_status, run_checks
except ModuleNotFoundError:
    from validation_runner import enforce_parser_artifact_contracts, format_status, run_checks


ROOT_DIR = Path(__file__).resolve().parents[2]
PATHWAYS_INPUT_PATH = ROOT_DIR / "data" / "processed" / "rules" / "appendix_iv_pathways.csv"
DECOMPOSED_INPUT_PATH = ROOT_DIR / "data" / "staged" / "raw_csv" / "appendix_iv_decomposed.csv"
APPLICABILITY_INPUT_PATH = ROOT_DIR / "data" / "processed" / "rules" / "appendix_iv_applicability.csv"

SOURCE_ID = UUID("a0000000-0000-0000-0000-000000000001")
HS_VERSION = "HS2017"
APPENDIX_VERSION = "December 2023 Compilation"
INSERT_BATCH_SIZE = 500


@dataclass(frozen=True, slots=True)
class PromotionPlan:
    pathway_csv_rows: list[dict[str, str]]
    decomposed_csv_rows: list[dict[str, str]]
    applicability_csv_rows: list[dict[str, str]]
    psr_rule_rows: list[dict[str, object]]
    component_rows: list[dict[str, object]]
    pathway_rows: list[dict[str, object]]
    applicability_rows: list[dict[str, object]]
    missing_component_rule_keys: list[str]
    missing_pathway_rule_keys: list[str]
    missing_psr_codes: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Promote staged Appendix IV parser artifacts into operational PSR tables."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build and validate the promotion plan without writing to the database.",
    )
    parser.add_argument(
        "--allow-partial-mappings",
        action="store_true",
        help="Allow promotion even if cross-artifact mappings are missing. Not recommended for normal runs.",
    )
    parser.add_argument(
        "--post-validate",
        action="store_true",
        help="Run database validation checks after a successful promotion.",
    )
    return parser.parse_args()


def read_rows(input_path: Path) -> list[dict[str, str]]:
    with input_path.open("r", newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def normalize_text(value: str | None) -> str:
    return " ".join(str(value or "").split())


def parse_int(value: str | None) -> int | None:
    raw_value = normalize_text(value)
    if not raw_value:
        return None
    return int(float(raw_value))


def parse_decimal(value: str | None) -> Decimal | None:
    raw_value = normalize_text(value)
    if not raw_value:
        return None
    return Decimal(raw_value)


def parse_bool(value: str | None) -> bool:
    return normalize_text(value).lower() == "true"


def parse_json(value: str | None) -> dict[str, object]:
    return json.loads(value or "{}")


def parse_rule_status(value: str | None) -> RuleStatusEnum:
    raw_value = normalize_text(value) or RuleStatusEnum.AGREED.value
    return RuleStatusEnum(raw_value)


def parse_hs_level(value: str | None) -> HsLevelEnum:
    return HsLevelEnum(normalize_text(value))


def parse_component_type(value: str | None) -> RuleComponentTypeEnum:
    return RuleComponentTypeEnum(normalize_text(value))


def parse_operator_type(value: str | None) -> OperatorTypeEnum:
    return OperatorTypeEnum(normalize_text(value) or OperatorTypeEnum.STANDALONE.value)


def parse_threshold_basis(value: str | None) -> ThresholdBasisEnum | None:
    raw_value = normalize_text(value)
    if not raw_value:
        return None
    return ThresholdBasisEnum(raw_value)


def parse_tariff_shift_level(value: str | None) -> HsLevelEnum | None:
    raw_value = normalize_text(value)
    if not raw_value:
        return None
    return HsLevelEnum(raw_value)


def ensure_input_files_exist() -> None:
    for input_path in (PATHWAYS_INPUT_PATH, DECOMPOSED_INPUT_PATH, APPLICABILITY_INPUT_PATH):
        if not input_path.exists():
            raise FileNotFoundError(f"Required input CSV not found: {input_path}")


def pathway_rule_key(row: dict[str, str]) -> tuple[str, str, str, str, str, str]:
    return (
        normalize_text(row.get("hs_code")),
        normalize_text(row.get("hs_level")),
        normalize_text(row.get("product_description")),
        normalize_text(row.get("legal_rule_text_verbatim")),
        normalize_text(row.get("rule_status")),
        normalize_text(row.get("page_ref")),
    )


def decomposed_rule_key(row: dict[str, str]) -> tuple[str, str, str, str, str, str]:
    rule_status = RuleStatusEnum.PENDING.value if parse_bool(row.get("pending_flag")) else RuleStatusEnum.AGREED.value
    return (
        normalize_text(row.get("hs_code")),
        normalize_text(row.get("hs_level")),
        normalize_text(row.get("raw_description")),
        normalize_text(row.get("raw_rule_text")),
        rule_status,
        normalize_text(row.get("page_num")),
    )


def build_row_ref(rule_key: tuple[str, str, str, str, str, str]) -> str:
    digest = hashlib.sha256("|".join(rule_key).encode("utf-8")).hexdigest()[:16]
    return f"parser-{digest}"


def ordered_unique_rules(pathway_rows: list[dict[str, str]]) -> OrderedDict[tuple[str, str, str, str, str, str], dict[str, str]]:
    rules: OrderedDict[tuple[str, str, str, str, str, str], dict[str, str]] = OrderedDict()
    for row in pathway_rows:
        key = pathway_rule_key(row)
        if key not in rules:
            rules[key] = row
    return rules


def build_psr_rule_rows(pathway_rows: list[dict[str, str]]) -> tuple[list[dict[str, object]], dict[tuple[str, str, str, str, str, str], UUID], OrderedDict[str, UUID]]:
    unique_rules = ordered_unique_rules(pathway_rows)
    rows: list[dict[str, object]] = []
    rule_id_map: dict[tuple[str, str, str, str, str, str], UUID] = {}
    first_psr_id_by_hs_code: OrderedDict[str, UUID] = OrderedDict()

    for rule_key, row in unique_rules.items():
        psr_id = uuid4()
        rule_id_map[rule_key] = psr_id
        hs_code = rule_key[0]
        if hs_code and hs_code not in first_psr_id_by_hs_code:
            first_psr_id_by_hs_code[hs_code] = psr_id

        rows.append(
            {
                "psr_id": psr_id,
                "source_id": SOURCE_ID,
                "appendix_version": APPENDIX_VERSION,
                "hs_version": HS_VERSION,
                "hs_code": hs_code,
                "hs_code_start": None,
                "hs_code_end": None,
                "hs_level": parse_hs_level(row.get("hs_level")),
                "product_description": normalize_text(row.get("product_description")),
                "legal_rule_text_verbatim": normalize_text(row.get("legal_rule_text_verbatim")),
                "legal_rule_text_normalized": normalize_text(row.get("legal_rule_text_verbatim")),
                "rule_status": parse_rule_status(row.get("rule_status")),
                "effective_date": None,
                "page_ref": parse_int(row.get("page_ref")),
                "table_ref": None,
                "row_ref": build_row_ref(rule_key),
            }
        )

    return rows, rule_id_map, first_psr_id_by_hs_code


def build_component_rows(
    decomposed_rows: list[dict[str, str]],
    rule_id_map: dict[tuple[str, str, str, str, str, str], UUID],
) -> tuple[list[dict[str, object]], list[str]]:
    rows: list[dict[str, object]] = []
    missing_rule_keys: list[str] = []

    for row in decomposed_rows:
        rule_key = decomposed_rule_key(row)
        psr_id = rule_id_map.get(rule_key)
        if psr_id is None:
            missing_rule_keys.append("|".join(rule_key))
            continue

        component_text = normalize_text(row.get("specific_process_text")) or normalize_text(row.get("raw_rule_text"))
        rows.append(
            {
                "component_id": uuid4(),
                "psr_id": psr_id,
                "component_type": parse_component_type(row.get("component_type")),
                "operator_type": parse_operator_type(row.get("operator_type")),
                "threshold_percent": parse_decimal(row.get("threshold_percent")),
                "threshold_basis": parse_threshold_basis(row.get("threshold_basis")),
                "tariff_shift_level": parse_tariff_shift_level(row.get("tariff_shift_level")),
                "specific_process_text": normalize_text(row.get("specific_process_text")) or None,
                "component_text_verbatim": component_text,
                "normalized_expression": normalize_text(row.get("normalized_expression")) or None,
                "confidence_score": parse_decimal(row.get("confidence_score")) or Decimal("0.000"),
                "component_order": parse_int(row.get("component_order")) or 1,
            }
        )

    return rows, missing_rule_keys


def build_pathway_rows(
    pathway_rows: list[dict[str, str]],
    rule_id_map: dict[tuple[str, str, str, str, str, str], UUID],
) -> tuple[list[dict[str, object]], list[str]]:
    rows: list[dict[str, object]] = []
    missing_rule_keys: list[str] = []

    for row in pathway_rows:
        rule_key = pathway_rule_key(row)
        psr_id = rule_id_map.get(rule_key)
        if psr_id is None:
            missing_rule_keys.append("|".join(rule_key))
            continue

        expression_payload = parse_json(row.get("expression_json"))
        rows.append(
            {
                "pathway_id": uuid4(),
                "psr_id": psr_id,
                "pathway_code": normalize_text(row.get("pathway_code")),
                "pathway_label": normalize_text(row.get("pathway_label")),
                "pathway_type": normalize_text(row.get("pathway_type")) or "specific",
                "expression_json": expression_payload,
                "threshold_percent": parse_decimal(row.get("threshold_percent")),
                "threshold_basis": parse_threshold_basis(row.get("threshold_basis")),
                "tariff_shift_level": parse_tariff_shift_level(row.get("tariff_shift_level")),
                "required_process_text": None,
                "allows_cumulation": parse_bool(row.get("allows_cumulation")),
                "allows_tolerance": parse_bool(row.get("allows_tolerance")),
                "priority_rank": parse_int(row.get("priority_rank")) or 1,
                "effective_date": None,
                "expiry_date": None,
            }
        )

    return rows, missing_rule_keys


def build_applicability_rows(
    applicability_rows: list[dict[str, str]],
    first_psr_id_by_hs_code: OrderedDict[str, UUID],
) -> tuple[list[dict[str, object]], list[str]]:
    rows: list[dict[str, object]] = []
    missing_psr_codes: list[str] = []

    for row in applicability_rows:
        psr_hs_code = normalize_text(row.get("psr_hs_code"))
        psr_id = first_psr_id_by_hs_code.get(psr_hs_code)
        if psr_id is None:
            missing_psr_codes.append(psr_hs_code)
            continue

        rows.append(
            {
                "applicability_id": uuid4(),
                "hs6_id": UUID(normalize_text(row.get("hs6_id"))),
                "psr_id": psr_id,
                "applicability_type": normalize_text(row.get("applicability_type")),
                "priority_rank": parse_int(row.get("priority_rank")) or 1,
                "effective_date": None,
                "expiry_date": None,
            }
        )

    return rows, missing_psr_codes


def format_samples(values: list[str], *, limit: int = 3) -> str:
    if not values:
        return ""
    sample = values[:limit]
    suffix = "" if len(values) <= limit else f" ... (+{len(values) - limit} more)"
    return ", ".join(sample) + suffix


def ensure_mapping_consistency(
    *,
    missing_component_rule_keys: list[str],
    missing_pathway_rule_keys: list[str],
    missing_psr_codes: list[str],
    allow_partial_mappings: bool,
) -> None:
    if allow_partial_mappings:
        return

    failures: list[str] = []
    if missing_component_rule_keys:
        failures.append(
            "component-to-rule mappings missing: "
            f"{len(missing_component_rule_keys)} rows ({format_samples(missing_component_rule_keys)})"
        )
    if missing_pathway_rule_keys:
        failures.append(
            "pathway-to-rule mappings missing: "
            f"{len(missing_pathway_rule_keys)} rows ({format_samples(missing_pathway_rule_keys)})"
        )
    if missing_psr_codes:
        failures.append(
            "applicability-to-rule mappings missing: "
            f"{len(missing_psr_codes)} rows ({format_samples(missing_psr_codes)})"
        )

    if failures:
        raise RuntimeError(
            "Promotion plan is incomplete. Resolve staged artifact mismatches before promotion, "
            "or rerun with --allow-partial-mappings if you explicitly want to accept partial promotion.\n"
            + "\n".join(f"- {failure}" for failure in failures)
        )


def build_promotion_plan(*, allow_partial_mappings: bool) -> PromotionPlan:
    ensure_input_files_exist()

    pathway_csv_rows = read_rows(PATHWAYS_INPUT_PATH)
    decomposed_csv_rows = read_rows(DECOMPOSED_INPUT_PATH)
    applicability_csv_rows = read_rows(APPLICABILITY_INPUT_PATH)

    enforce_parser_artifact_contracts(
        decomposed_rows=decomposed_csv_rows,
        pathway_rows=pathway_csv_rows,
        applicability_rows=applicability_csv_rows,
    )

    psr_rule_rows, rule_id_map, first_psr_id_by_hs_code = build_psr_rule_rows(pathway_csv_rows)
    component_rows, missing_component_rule_keys = build_component_rows(decomposed_csv_rows, rule_id_map)
    pathway_rows, missing_pathway_rule_keys = build_pathway_rows(pathway_csv_rows, rule_id_map)
    applicability_rows, missing_psr_codes = build_applicability_rows(applicability_csv_rows, first_psr_id_by_hs_code)

    ensure_mapping_consistency(
        missing_component_rule_keys=missing_component_rule_keys,
        missing_pathway_rule_keys=missing_pathway_rule_keys,
        missing_psr_codes=missing_psr_codes,
        allow_partial_mappings=allow_partial_mappings,
    )

    return PromotionPlan(
        pathway_csv_rows=pathway_csv_rows,
        decomposed_csv_rows=decomposed_csv_rows,
        applicability_csv_rows=applicability_csv_rows,
        psr_rule_rows=psr_rule_rows,
        component_rows=component_rows,
        pathway_rows=pathway_rows,
        applicability_rows=applicability_rows,
        missing_component_rule_keys=missing_component_rule_keys,
        missing_pathway_rule_keys=missing_pathway_rule_keys,
        missing_psr_codes=missing_psr_codes,
    )


def print_promotion_plan(plan: PromotionPlan, *, dry_run: bool) -> None:
    print("PSR promotion plan")
    print(f"- Mode: {'dry-run' if dry_run else 'promote'}")
    print(f"- Input artifacts: {DECOMPOSED_INPUT_PATH.name}, {PATHWAYS_INPUT_PATH.name}, {APPLICABILITY_INPUT_PATH.name}")
    print(f"- Decomposed rows: {len(plan.decomposed_csv_rows)}")
    print(f"- Pathway rows: {len(plan.pathway_csv_rows)}")
    print(f"- Applicability rows: {len(plan.applicability_csv_rows)}")
    print(f"- Planned psr_rule rows: {len(plan.psr_rule_rows)}")
    print(f"- Planned psr_rule_component rows: {len(plan.component_rows)}")
    print(f"- Planned eligibility_rule_pathway rows: {len(plan.pathway_rows)}")
    print(f"- Planned hs6_psr_applicability rows: {len(plan.applicability_rows)}")
    print(
        "- Cross-artifact mapping gaps: "
        f"components={len(plan.missing_component_rule_keys)}, "
        f"pathways={len(plan.missing_pathway_rule_keys)}, "
        f"applicability={len(plan.missing_psr_codes)}"
    )


async def ensure_source_exists(session) -> None:
    source_exists = await session.scalar(
        text("SELECT 1 FROM source_registry WHERE source_id = :source_id LIMIT 1"),
        {"source_id": SOURCE_ID},
    )
    if source_exists is None:
        raise RuntimeError(
            "Appendix IV source row not found. Seed source_registry before running this script."
        )


async def clear_existing_rows(session) -> None:
    statements = [
        "DELETE FROM hs6_psr_applicability WHERE psr_id IN (SELECT psr_id FROM psr_rule WHERE source_id = :source_id)",
        "DELETE FROM eligibility_rule_pathway WHERE psr_id IN (SELECT psr_id FROM psr_rule WHERE source_id = :source_id)",
        "DELETE FROM psr_rule_component WHERE psr_id IN (SELECT psr_id FROM psr_rule WHERE source_id = :source_id)",
        "DELETE FROM psr_rule WHERE source_id = :source_id",
    ]
    for sql in statements:
        await session.execute(text(sql), {"source_id": SOURCE_ID})


def chunked_rows(rows: list[dict[str, object]], batch_size: int) -> list[list[dict[str, object]]]:
    return [rows[index : index + batch_size] for index in range(0, len(rows), batch_size)]


async def insert_rows(session, model, rows: list[dict[str, object]], returning_column) -> int:
    if not rows:
        return 0

    inserted_count = 0
    for batch in chunked_rows(rows, INSERT_BATCH_SIZE):
        statement = insert(model).values(batch).on_conflict_do_nothing().returning(returning_column)
        result = await session.execute(statement)
        inserted_count += len(result.scalars().all())
    return inserted_count


async def execute_promotion_plan(plan: PromotionPlan) -> tuple[int, int, int, int]:
    session_factory = get_async_session_factory()
    inserted_rules = 0
    inserted_components = 0
    inserted_pathways = 0
    inserted_applicability = 0

    try:
        async with session_factory() as session:
            async with session.begin():
                await ensure_source_exists(session)
                await clear_existing_rows(session)

                inserted_rules = await insert_rows(session, PSRRule, plan.psr_rule_rows, PSRRule.psr_id)
                inserted_components = await insert_rows(session, PSRRuleComponent, plan.component_rows, PSRRuleComponent.component_id)
                inserted_pathways = await insert_rows(session, EligibilityRulePathway, plan.pathway_rows, EligibilityRulePathway.pathway_id)
                inserted_applicability = await insert_rows(session, HS6PSRApplicability, plan.applicability_rows, HS6PSRApplicability.applicability_id)
    except IntegrityError as exc:
        print(f"FK/constraint error during insert: {exc}")
        raise

    return inserted_rules, inserted_components, inserted_pathways, inserted_applicability


async def run_post_validation() -> int:
    db_results = await run_checks()
    print("Post-promotion database validation")
    for result in db_results:
        print(f"- {format_status(result.passed)}: {result.name} ({result.detail})")
    return sum(1 for result in db_results if not result.passed)


async def main() -> int:
    args = parse_args()
    plan = build_promotion_plan(allow_partial_mappings=args.allow_partial_mappings)
    print_promotion_plan(plan, dry_run=args.dry_run)

    if args.dry_run:
        print("Promotion dry-run completed. No database changes were made.")
        return 0

    inserted_rules, inserted_components, inserted_pathways, inserted_applicability = await execute_promotion_plan(plan)

    print("PSR parser promotion summary")
    print(f"- Rules inserted: {inserted_rules}")
    print(f"- Components inserted: {inserted_components}")
    print(f"- Pathways inserted: {inserted_pathways}")
    print(f"- Applicability rows inserted: {inserted_applicability}")
    print("- Existing Appendix IV source rows were cleared and replaced atomically inside one transaction")

    if args.post_validate:
        fail_count = await run_post_validation()
        return 0 if fail_count == 0 else 1

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
