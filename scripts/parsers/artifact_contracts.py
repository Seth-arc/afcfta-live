from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ArtifactValidationIssue:
    artifact_type: str
    row_number: int
    field: str
    message: str
    row_key: str = ""
    value: str = ""

    def render(self) -> str:
        parts = [f"{self.artifact_type} row {self.row_number}", self.field, self.message]
        if self.row_key:
            parts.append(f"key={self.row_key}")
        if self.value:
            parts.append(f"value={self.value}")
        return " | ".join(parts)


@dataclass(frozen=True, slots=True)
class ArtifactValidationResult:
    artifact_type: str
    total_rows: int
    issues: tuple[ArtifactValidationIssue, ...]

    @property
    def passed(self) -> bool:
        return not self.issues

    @property
    def invalid_rows(self) -> int:
        return len({issue.row_number for issue in self.issues})


class ParserArtifactValidationError(RuntimeError):
    def __init__(self, results: list[ArtifactValidationResult], max_examples: int = 12) -> None:
        details: list[str] = []
        for result in results:
            details.append(
                f"{result.artifact_type}: {result.invalid_rows} invalid rows across {len(result.issues)} issues"
            )
            for issue in result.issues[:max_examples]:
                details.append(f"- {issue.render()}")
            if len(result.issues) > max_examples:
                details.append(
                    f"- ... {len(result.issues) - max_examples} more {result.artifact_type} issues omitted"
                )
        super().__init__(
            "Parser artifact validation failed. Promotion aborted.\n" + "\n".join(details)
        )


def normalize_text(value: object | None) -> str:
    return " ".join(str(value or "").split())


def parse_int(value: object | None) -> int | None:
    raw_value = normalize_text(value)
    if not raw_value:
        return None
    try:
        return int(float(raw_value))
    except ValueError:
        return None


def parse_float(value: object | None) -> float | None:
    raw_value = normalize_text(value)
    if not raw_value:
        return None
    try:
        return float(raw_value)
    except ValueError:
        return None


def parse_bool_string(value: object | None) -> bool | None:
    raw_value = normalize_text(value).lower()
    if not raw_value:
        return None
    if raw_value == "true":
        return True
    if raw_value == "false":
        return False
    return None
