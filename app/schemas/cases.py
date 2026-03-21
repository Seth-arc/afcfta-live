"""Pydantic schemas for case creation and typed fact capture."""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.countries import V01_COUNTRIES
from app.core.enums import FactSourceTypeEnum, FactValueTypeEnum, PersonaModeEnum


def _normalize_hs6_code(value: str) -> str:
    digits_only = "".join(char for char in value if char.isdigit())
    if len(digits_only) < 6:
        raise ValueError("HS code must contain at least 6 digits")
    return digits_only[:6]


class CaseFactIn(BaseModel):
    """Typed fact submitted for a case."""

    fact_type: str
    fact_key: str
    fact_value_type: FactValueTypeEnum
    fact_value_text: str | None = None
    fact_value_number: float | None = None
    fact_value_boolean: bool | None = None
    fact_value_date: date | None = None
    fact_value_json: Any | None = None
    unit: str | None = None
    source_type: FactSourceTypeEnum | None = None
    source_ref: str | None = Field(
        default=None,
        validation_alias=AliasChoices("source_ref", "source_reference"),
        serialization_alias="source_ref",
    )
    confidence_score: float | None = Field(default=None, ge=0, le=1)
    fact_order: int | None = Field(default=None, ge=1)

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def validate_typed_value(self) -> "CaseFactIn":
        populated_fields = {
            "text": self.fact_value_text is not None,
            "number": self.fact_value_number is not None,
            "boolean": self.fact_value_boolean is not None,
            "date": self.fact_value_date is not None,
            "json": self.fact_value_json is not None,
            "list": self.fact_value_json is not None,
        }
        if not any(populated_fields.values()):
            raise ValueError("at least one typed fact value must be provided")
        if not populated_fields[self.fact_value_type.value]:
            raise ValueError("fact_value_type must match a populated value field")
        if self.fact_value_type == FactValueTypeEnum.LIST and not isinstance(self.fact_value_json, list):
            raise ValueError("fact_value_json must be a list when fact_value_type is 'list'")
        return self


class CaseCreateRequest(BaseModel):
    """API payload for creating a case and its initial facts."""

    case_external_ref: str
    exporter_state: str = Field(min_length=3, max_length=3)
    importer_state: str = Field(min_length=3, max_length=3)
    hs_version: str = "HS2017"
    hs6_code: str = Field(
        validation_alias=AliasChoices("hs6_code", "hs_code"),
        serialization_alias="hs6_code",
    )
    persona_mode: PersonaModeEnum
    facts: list[CaseFactIn]

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("exporter_state", "importer_state")
    @classmethod
    def validate_country_code(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in V01_COUNTRIES:
            raise ValueError("country code must be one of the v0.1 supported ISO alpha-3 values")
        return normalized

    @field_validator("hs6_code")
    @classmethod
    def normalize_hs6_code(cls, value: str) -> str:
        return _normalize_hs6_code(value)


class CaseCreateResponse(BaseModel):
    """Minimal API response after creating a case."""

    case_id: str
    case_external_ref: str
    hs6_code: str = Field(
        validation_alias=AliasChoices("hs6_code", "hs_code"),
        serialization_alias="hs6_code",
    )
    exporter_state: str
    importer_state: str

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("hs6_code")
    @classmethod
    def normalize_hs6_code(cls, value: str) -> str:
        return _normalize_hs6_code(value)
