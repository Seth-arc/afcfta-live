from __future__ import annotations

import asyncio
import csv
import hashlib
import json
from collections import OrderedDict
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from app.core.enums import HsLevelEnum, OperatorTypeEnum, RuleComponentTypeEnum, RuleStatusEnum, ThresholdBasisEnum
from app.db.base import get_async_session_factory
from app.db.models.rules import EligibilityRulePathway, HS6PSRApplicability, PSRRule, PSRRuleComponent


ROOT_DIR = Path(__file__).resolve().parents[2]
PATHWAYS_INPUT_PATH = ROOT_DIR / "data" / "processed" / "rules" / "appendix_iv_pathways.csv"
DECOMPOSED_INPUT_PATH = ROOT_DIR / "data" / "staged" / "raw_csv" / "appendix_iv_decomposed.csv"
APPLICABILITY_INPUT_PATH = ROOT_DIR / "data" / "processed" / "rules" / "appendix_iv_applicability.csv"

SOURCE_ID = UUID("a0000000-0000-0000-0000-000000000001")
HS_VERSION = "HS2017"
APPENDIX_VERSION = "December 2023 Compilation"
INSERT_BATCH_SIZE = 500


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
    digest = hashlib.sha1("|".join(rule_key).encode("utf-8")).hexdigest()[:16]
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


async def main() -> int:
    for input_path in (PATHWAYS_INPUT_PATH, DECOMPOSED_INPUT_PATH, APPLICABILITY_INPUT_PATH):
        if not input_path.exists():
            raise FileNotFoundError(f"Required input CSV not found: {input_path}")

    pathway_csv_rows = read_rows(PATHWAYS_INPUT_PATH)
    decomposed_csv_rows = read_rows(DECOMPOSED_INPUT_PATH)
    applicability_csv_rows = read_rows(APPLICABILITY_INPUT_PATH)

    psr_rule_rows, rule_id_map, first_psr_id_by_hs_code = build_psr_rule_rows(pathway_csv_rows)
    component_rows, missing_component_rule_keys = build_component_rows(decomposed_csv_rows, rule_id_map)
    pathway_rows, missing_pathway_rule_keys = build_pathway_rows(pathway_csv_rows, rule_id_map)
    applicability_rows, missing_psr_codes = build_applicability_rows(applicability_csv_rows, first_psr_id_by_hs_code)

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

                inserted_rules = await insert_rows(session, PSRRule, psr_rule_rows, PSRRule.psr_id)
                inserted_components = await insert_rows(session, PSRRuleComponent, component_rows, PSRRuleComponent.component_id)
                inserted_pathways = await insert_rows(session, EligibilityRulePathway, pathway_rows, EligibilityRulePathway.pathway_id)
                inserted_applicability = await insert_rows(session, HS6PSRApplicability, applicability_rows, HS6PSRApplicability.applicability_id)
    except IntegrityError as exc:
        print(f"FK/constraint error during insert: {exc}")
        raise

    print("PSR parser insert summary")
    print(f"- Rules inserted: {inserted_rules}")
    print(f"- Components inserted: {inserted_components}")
    print(f"- Pathways inserted: {inserted_pathways}")
    print(f"- Applicability rows inserted: {inserted_applicability}")
    if missing_component_rule_keys:
        print(f"- Component rows skipped due to missing rule mapping: {len(missing_component_rule_keys)}")
    if missing_pathway_rule_keys:
        print(f"- Pathway rows skipped due to missing rule mapping: {len(missing_pathway_rule_keys)}")
    if missing_psr_codes:
        print(f"- Applicability rows skipped due to unmapped psr_hs_code: {len(missing_psr_codes)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))