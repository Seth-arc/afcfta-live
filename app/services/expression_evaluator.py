"""Safely parse and resolve text and JSON pathway expressions."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
import re
from typing import Any

from app.core.exceptions import ExpressionEvaluationError
from app.core.fact_keys import DERIVED_VARIABLES, PRODUCTION_FACTS
from app.core.failure_codes import FAILURE_CODES

MAX_EXPRESSION_DEPTH = 10
MAX_TEXT_EXPRESSION_LENGTH = 500
ALLOWED_VARIABLES = set(PRODUCTION_FACTS) | set(DERIVED_VARIABLES)
SPECIAL_VARIABLES = {"non_originating_inputs", "output_hs6_code"}
TEXT_OPERATOR_MAP = {
    "<=": "FORMULA_LTE",
    "<": "FORMULA_LT",
    ">=": "FORMULA_GTE",
    ">": "FORMULA_GT",
    "==": "FACT_EQ",
    "!=": "FACT_NE",
}
JSON_OPERATORS = {
    "all",
    "any",
    "formula_lte",
    "formula_gte",
    "fact_eq",
    "fact_ne",
    "every_non_originating_input",
    "heading_ne_output",
    "subheading_ne_output",
}
TOKEN_PATTERN = re.compile(
    r"""
    \s*
    (?:
        (?P<COMPARATOR><=|>=|==|!=|<|>)
        |(?P<LOGICAL>\bAND\b|\bOR\b)
        |(?P<BOOLEAN>\btrue\b|\bfalse\b)
        |(?P<NUMBER>\d+(?:\.\d+)?)
        |(?P<IDENT>[A-Za-z_][A-Za-z0-9_]*)
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)
_MISSING = object()


@dataclass(slots=True)
class AtomicCheck:
    """Single leaf-check outcome for audit persistence."""

    check_code: str
    passed: bool | None
    expected_value: str
    observed_value: str
    explanation: str


@dataclass(slots=True)
class ExpressionResult:
    """Full evaluator result including missing facts and atomic checks."""

    result: bool | None
    evaluated_expression: str
    missing_variables: list[str] = field(default_factory=list)
    checks: list[AtomicCheck] = field(default_factory=list)


@dataclass(slots=True)
class Token:
    """Typed token extracted from a simple text expression."""

    kind: str
    value: str


@dataclass(slots=True)
class OperandNode:
    """Parsed operand for text expressions."""

    kind: str
    value: Any


@dataclass(slots=True)
class ComparisonNode:
    """Binary comparison node in a parsed text expression."""

    left: OperandNode
    operator: str
    right: OperandNode


@dataclass(slots=True)
class LogicalNode:
    """N-ary logical node in a parsed text expression."""

    operator: str
    operands: list[ComparisonNode | "LogicalNode"]


@dataclass(slots=True)
class ResolvedOperand:
    """Resolved operand value with provenance for audit output."""

    source_name: str
    value: Any
    is_variable: bool
    missing_variables: list[str] = field(default_factory=list)


class ExpressionEvaluator:
    """Evaluate supported text expressions and JSON expression trees safely."""

    def evaluate(self, expression: str | dict[str, Any], facts: dict[str, Any]) -> ExpressionResult:
        """Evaluate one text or JSON expression against normalized facts."""

        if isinstance(expression, str):
            parsed_expression = self._parse_text_expression(expression)
            return self._evaluate_text_node(parsed_expression, facts, depth=1)
        if isinstance(expression, dict):
            self._validate_json_node(expression, depth=1)
            return self._evaluate_json_node(expression, facts, depth=1)
        raise ExpressionEvaluationError(
            "Expression must be a text string or a JSON object",
            detail={"expression_type": type(expression).__name__},
        )

    def _parse_text_expression(self, expression: str) -> ComparisonNode | LogicalNode:
        """Tokenize and parse the simple text expression grammar."""

        expression = expression.strip()
        if len(expression) > MAX_TEXT_EXPRESSION_LENGTH:
            raise ExpressionEvaluationError(
                "Text expression exceeds maximum length of 500 characters",
                detail={"length": len(expression)},
            )

        tokens = self._tokenize_text_expression(expression)
        if not tokens:
            raise ExpressionEvaluationError("Text expression cannot be empty")

        node, position = self._parse_or_expression(tokens, 0)
        if position != len(tokens):
            raise ExpressionEvaluationError(
                "Unexpected trailing tokens in text expression",
                detail={"token": tokens[position].value},
            )
        if self._text_node_depth(node) > MAX_EXPRESSION_DEPTH:
            raise ExpressionEvaluationError("Expression exceeds maximum depth of 10 levels")
        return node

    def _tokenize_text_expression(self, expression: str) -> list[Token]:
        """Convert a simple text expression into a flat token stream."""

        tokens: list[Token] = []
        position = 0
        while position < len(expression):
            match = TOKEN_PATTERN.match(expression, position)
            if not match:
                snippet = expression[position : position + 25]
                raise ExpressionEvaluationError(
                    "Invalid token in text expression",
                    detail={"snippet": snippet},
                )

            position = match.end()
            kind = match.lastgroup
            if kind is None:
                continue
            value = match.group(kind)
            if kind == "BOOLEAN":
                tokens.append(Token(kind, value.lower()))
            elif kind == "LOGICAL":
                tokens.append(Token(kind, value.upper()))
            else:
                tokens.append(Token(kind, value))

        return tokens

    def _parse_or_expression(
        self,
        tokens: list[Token],
        position: int,
    ) -> tuple[ComparisonNode | LogicalNode, int]:
        """Parse OR-separated expressions with lower precedence than AND."""

        node, position = self._parse_and_expression(tokens, position)
        operands = [node]
        while position < len(tokens) and tokens[position].kind == "LOGICAL":
            if tokens[position].value != "OR":
                break
            right_node, position = self._parse_and_expression(tokens, position + 1)
            operands.append(right_node)
        if len(operands) == 1:
            return node, position
        return LogicalNode(operator="OR", operands=operands), position

    def _parse_and_expression(
        self,
        tokens: list[Token],
        position: int,
    ) -> tuple[ComparisonNode | LogicalNode, int]:
        """Parse AND-separated expressions with higher precedence than OR."""

        node, position = self._parse_comparison(tokens, position)
        operands = [node]
        while position < len(tokens) and tokens[position].kind == "LOGICAL":
            if tokens[position].value != "AND":
                break
            right_node, position = self._parse_comparison(tokens, position + 1)
            operands.append(right_node)
        if len(operands) == 1:
            return node, position
        return LogicalNode(operator="AND", operands=operands), position

    def _parse_comparison(
        self,
        tokens: list[Token],
        position: int,
    ) -> tuple[ComparisonNode, int]:
        """Parse one binary comparison expression."""

        left_operand, position = self._parse_operand(tokens, position)
        if position >= len(tokens) or tokens[position].kind != "COMPARATOR":
            raise ExpressionEvaluationError("Text expression is missing a comparison operator")
        operator = tokens[position].value
        right_operand, position = self._parse_operand(tokens, position + 1)
        return ComparisonNode(left=left_operand, operator=operator, right=right_operand), position

    def _parse_operand(self, tokens: list[Token], position: int) -> tuple[OperandNode, int]:
        """Parse a variable reference, boolean literal, or numeric literal."""

        if position >= len(tokens):
            raise ExpressionEvaluationError("Unexpected end of text expression")

        token = tokens[position]
        if token.kind == "IDENT":
            return OperandNode(kind="IDENT", value=token.value), position + 1
        if token.kind == "BOOLEAN":
            return OperandNode(kind="BOOLEAN", value=token.value == "true"), position + 1
        if token.kind == "NUMBER":
            return OperandNode(kind="NUMBER", value=Decimal(token.value)), position + 1
        raise ExpressionEvaluationError(
            "Invalid operand in text expression",
            detail={"token": token.value},
        )

    def _evaluate_text_node(
        self,
        node: ComparisonNode | LogicalNode,
        facts: dict[str, Any],
        *,
        depth: int,
    ) -> ExpressionResult:
        """Evaluate a parsed text expression tree."""

        self._assert_depth(depth)
        if isinstance(node, ComparisonNode):
            return self._evaluate_text_comparison(node, facts)

        child_results = [
            self._evaluate_text_node(child, facts, depth=depth + 1) for child in node.operands
        ]
        return self._combine_logical_results(node.operator, child_results)

    def _evaluate_text_comparison(
        self,
        node: ComparisonNode,
        facts: dict[str, Any],
    ) -> ExpressionResult:
        """Evaluate one text comparison node."""

        left_operand = self._resolve_text_operand(node.left, facts)
        right_operand = self._resolve_text_operand(node.right, facts)
        return self._build_comparison_result(
            left_operand=left_operand,
            operator=node.operator,
            right_operand=right_operand,
            check_code=TEXT_OPERATOR_MAP[node.operator],
        )

    def _resolve_text_operand(self, node: OperandNode, facts: dict[str, Any]) -> ResolvedOperand:
        """Resolve a parsed text operand against the facts dict."""

        if node.kind == "IDENT":
            value, missing_variables = self._resolve_variable(node.value, facts)
            return ResolvedOperand(
                source_name=node.value,
                value=value,
                is_variable=True,
                missing_variables=missing_variables,
            )
        return ResolvedOperand(
            source_name=self._format_value(node.value),
            value=node.value,
            is_variable=False,
        )

    def _validate_json_node(self, node: Any, *, depth: int) -> None:
        """Validate JSON expression structure recursively against the spec."""

        self._assert_depth(depth)
        if not isinstance(node, dict):
            raise ExpressionEvaluationError("expression_json nodes must be objects")

        op = node.get("op")
        if not isinstance(op, str) or op not in JSON_OPERATORS:
            raise ExpressionEvaluationError(
                f"Unsupported expression_json op '{op}'",
                detail={"op": op},
            )

        if op in {"all", "any"}:
            args = node.get("args")
            if not isinstance(args, list) or not args:
                raise ExpressionEvaluationError(
                    f"expression_json op '{op}' requires a non-empty args list",
                    detail={"op": op},
                )
            for child in args:
                self._validate_json_node(child, depth=depth + 1)
            return

        if op in {"formula_lte", "formula_gte"}:
            formula = node.get("formula")
            if not isinstance(formula, str):
                raise ExpressionEvaluationError(f"expression_json op '{op}' requires formula")
            self._ensure_allowed_variable(formula, allow_special=False)
            if formula not in DERIVED_VARIABLES:
                raise ExpressionEvaluationError(
                    f"Formula '{formula}' is not a supported derived variable",
                    detail={"formula": formula},
                )
            self._ensure_numeric_literal(node.get("value"), field_name="value")
            return

        if op == "fact_eq":
            fact_name = node.get("fact")
            if not isinstance(fact_name, str):
                raise ExpressionEvaluationError("expression_json op 'fact_eq' requires fact")
            self._ensure_allowed_variable(fact_name, allow_special=False)
            if "value" not in node:
                raise ExpressionEvaluationError("expression_json op 'fact_eq' requires value")
            return

        if op == "fact_ne":
            fact_name = node.get("fact")
            if not isinstance(fact_name, str):
                raise ExpressionEvaluationError("expression_json op 'fact_ne' requires fact")
            self._ensure_allowed_variable(fact_name, allow_special=False)
            has_value = "value" in node
            has_ref_fact = "ref_fact" in node
            if has_value == has_ref_fact:
                raise ExpressionEvaluationError(
                    "expression_json op 'fact_ne' requires exactly one of value or ref_fact"
                )
            if has_ref_fact:
                ref_fact = node.get("ref_fact")
                if not isinstance(ref_fact, str):
                    raise ExpressionEvaluationError(
                        "expression_json op 'fact_ne' requires ref_fact to be a string"
                    )
                self._ensure_allowed_variable(ref_fact, allow_special=False)
            return

        if op == "every_non_originating_input":
            test_node = node.get("test")
            if not isinstance(test_node, dict):
                raise ExpressionEvaluationError(
                    "expression_json op 'every_non_originating_input' requires test object"
                )
            test_op = test_node.get("op")
            if test_op not in {"heading_ne_output", "subheading_ne_output"}:
                raise ExpressionEvaluationError(
                    f"Unsupported every_non_originating_input test op '{test_op}'",
                    detail={"op": test_op},
                )
            self._assert_depth(depth + 1)

    def _evaluate_json_node(
        self,
        node: dict[str, Any],
        facts: dict[str, Any],
        *,
        depth: int,
    ) -> ExpressionResult:
        """Evaluate a validated JSON expression tree recursively."""

        self._assert_depth(depth)
        op = node["op"]
        if op == "all":
            child_results = [
                self._evaluate_json_node(child, facts, depth=depth + 1) for child in node["args"]
            ]
            return self._combine_logical_results("AND", child_results)
        if op == "any":
            child_results = [
                self._evaluate_json_node(child, facts, depth=depth + 1) for child in node["args"]
            ]
            return self._combine_logical_results("OR", child_results)
        if op == "formula_lte":
            return self._evaluate_formula_comparison(
                formula=node["formula"],
                operator="<=",
                threshold=node["value"],
                facts=facts,
                check_code="FORMULA_LTE",
            )
        if op == "formula_gte":
            return self._evaluate_formula_comparison(
                formula=node["formula"],
                operator=">=",
                threshold=node["value"],
                facts=facts,
                check_code="FORMULA_GTE",
            )
        if op == "fact_eq":
            return self._evaluate_fact_value_comparison(
                fact_name=node["fact"],
                operator="==",
                value=node["value"],
                facts=facts,
                check_code="FACT_EQ",
            )
        if op == "fact_ne":
            if "ref_fact" in node:
                return self._evaluate_fact_reference_comparison(
                    fact_name=node["fact"],
                    operator="!=",
                    ref_fact=node["ref_fact"],
                    facts=facts,
                    check_code="FACT_NE",
                )
            return self._evaluate_fact_value_comparison(
                fact_name=node["fact"],
                operator="!=",
                value=node["value"],
                facts=facts,
                check_code="FACT_NE",
            )
        if op == "every_non_originating_input":
            return self._evaluate_every_non_originating_input(node["test"]["op"], facts)
        raise ExpressionEvaluationError(
            f"Unsupported expression_json op '{op}'",
            detail={"op": op},
        )

    def _evaluate_formula_comparison(
        self,
        *,
        formula: str,
        operator: str,
        threshold: Any,
        facts: dict[str, Any],
        check_code: str,
    ) -> ExpressionResult:
        """Evaluate a formula-to-threshold comparison."""

        resolved_value, missing_variables = self._resolve_variable(formula, facts)
        left_operand = ResolvedOperand(
            source_name=formula,
            value=resolved_value,
            is_variable=True,
            missing_variables=missing_variables,
        )
        right_operand = ResolvedOperand(
            source_name=self._format_value(threshold),
            value=self._coerce_numeric_value(threshold),
            is_variable=False,
        )
        return self._build_comparison_result(
            left_operand=left_operand,
            operator=operator,
            right_operand=right_operand,
            check_code=check_code,
        )

    def _evaluate_fact_value_comparison(
        self,
        *,
        fact_name: str,
        operator: str,
        value: Any,
        facts: dict[str, Any],
        check_code: str,
    ) -> ExpressionResult:
        """Evaluate a fact against a literal value."""

        resolved_value, missing_variables = self._resolve_variable(fact_name, facts)
        left_operand = ResolvedOperand(
            source_name=fact_name,
            value=resolved_value,
            is_variable=True,
            missing_variables=missing_variables,
        )
        right_operand = ResolvedOperand(
            source_name=self._format_value(value),
            value=value,
            is_variable=False,
        )
        return self._build_comparison_result(
            left_operand=left_operand,
            operator=operator,
            right_operand=right_operand,
            check_code=check_code,
        )

    def _evaluate_fact_reference_comparison(
        self,
        *,
        fact_name: str,
        operator: str,
        ref_fact: str,
        facts: dict[str, Any],
        check_code: str,
    ) -> ExpressionResult:
        """Evaluate a fact against another fact reference."""

        left_value, left_missing = self._resolve_variable(fact_name, facts)
        right_value, right_missing = self._resolve_variable(ref_fact, facts)
        return self._build_comparison_result(
            left_operand=ResolvedOperand(
                source_name=fact_name,
                value=left_value,
                is_variable=True,
                missing_variables=left_missing,
            ),
            operator=operator,
            right_operand=ResolvedOperand(
                source_name=ref_fact,
                value=right_value,
                is_variable=True,
                missing_variables=right_missing,
            ),
            check_code=check_code,
        )

    def _evaluate_every_non_originating_input(
        self,
        test_op: str,
        facts: dict[str, Any],
    ) -> ExpressionResult:
        """Evaluate the list-based CTH or CTSH check against the output HS code."""

        missing_variables: list[str] = []
        inputs = facts.get("non_originating_inputs")
        if inputs is None:
            missing_variables.append("non_originating_inputs")
        output_hs6_code = facts.get("output_hs6_code")
        if output_hs6_code is None:
            missing_variables.append("output_hs6_code")

        if missing_variables:
            return ExpressionResult(
                result=None,
                evaluated_expression=f"{test_op}(missing inputs)",
                missing_variables=missing_variables,
                checks=[
                    AtomicCheck(
                        check_code=test_op.upper(),
                        passed=None,
                        expected_value="required list and output HS6",
                        observed_value="missing",
                        explanation=f"Missing variable(s): {', '.join(missing_variables)}",
                    )
                ],
            )

        if not isinstance(inputs, list):
            raise ExpressionEvaluationError(
                "non_originating_inputs must be a list",
                detail={"type": type(inputs).__name__},
            )

        output_code = str(output_hs6_code)
        expected_segment = output_code[:4] if test_op == "heading_ne_output" else output_code[:6]
        observed_segments: list[str] = []
        for item in inputs:
            if not isinstance(item, dict):
                raise ExpressionEvaluationError(
                    "non_originating_inputs items must be objects",
                    detail={"item_type": type(item).__name__},
                )
            if test_op == "heading_ne_output":
                segment = item.get("hs4_code")
                if segment is None and item.get("hs6_code") is not None:
                    segment = str(item["hs6_code"])[:4]
            else:
                segment = item.get("hs6_code")
            if segment is None:
                raise ExpressionEvaluationError(
                    f"non_originating_inputs item missing required code for {test_op}",
                    detail={"test_op": test_op, "item": item},
                )
            observed_segments.append(str(segment))

        passed = all(segment != expected_segment for segment in observed_segments)
        check_code = (
            "HEADING_NE_OUTPUT" if test_op == "heading_ne_output" else "SUBHEADING_NE_OUTPUT"
        )
        explanation = self._build_non_originating_explanation(test_op, passed)
        observed_value = ", ".join(observed_segments) if observed_segments else "[]"
        evaluated_expression = f"{test_op}({observed_value} -> output {expected_segment})"
        return ExpressionResult(
            result=passed,
            evaluated_expression=evaluated_expression,
            missing_variables=[],
            checks=[
                AtomicCheck(
                    check_code=check_code,
                    passed=passed,
                    expected_value=f"all inputs != {expected_segment}",
                    observed_value=observed_value,
                    explanation=explanation,
                )
            ],
        )

    def _build_comparison_result(
        self,
        *,
        left_operand: ResolvedOperand,
        operator: str,
        right_operand: ResolvedOperand,
        check_code: str,
    ) -> ExpressionResult:
        """Build a consistent ExpressionResult for one comparison leaf."""

        missing_variables = self._merge_missing(
            left_operand.missing_variables,
            right_operand.missing_variables,
        )
        evaluated_expression = (
            f"{self._format_resolved_operand(left_operand)} {operator} "
            f"{self._format_resolved_operand(right_operand)}"
        )

        if missing_variables:
            return ExpressionResult(
                result=None,
                evaluated_expression=evaluated_expression,
                missing_variables=missing_variables,
                checks=[
                    AtomicCheck(
                        check_code=check_code,
                        passed=None,
                        expected_value=self._expected_value(right_operand),
                        observed_value=self._observed_value(left_operand),
                        explanation=f"Missing variable(s): {', '.join(missing_variables)}",
                    )
                ],
            )

        passed = self._compare_values(left_operand.value, operator, right_operand.value)
        return ExpressionResult(
            result=passed,
            evaluated_expression=evaluated_expression,
            missing_variables=[],
            checks=[
                AtomicCheck(
                    check_code=check_code,
                    passed=passed,
                    expected_value=self._expected_value(right_operand),
                    observed_value=self._observed_value(left_operand),
                    explanation=self._build_comparison_explanation(
                        left_operand.source_name,
                        operator,
                        right_operand.source_name,
                        passed,
                    ),
                )
            ],
        )

    def _combine_logical_results(
        self,
        logical_operator: str,
        child_results: list[ExpressionResult],
    ) -> ExpressionResult:
        """Combine leaf results using three-valued logical semantics."""

        results = [child.result for child in child_results]
        if logical_operator == "AND":
            if any(result is False for result in results):
                combined_result = False
            elif any(result is None for result in results):
                combined_result = None
            else:
                combined_result = True
        else:
            if any(result is True for result in results):
                combined_result = True
            elif any(result is None for result in results):
                combined_result = None
            else:
                combined_result = False

        joiner = f" {logical_operator} "
        return ExpressionResult(
            result=combined_result,
            evaluated_expression=joiner.join(
                f"({child.evaluated_expression})" for child in child_results
            ),
            missing_variables=self._merge_missing(
                *(child.missing_variables for child in child_results)
            ),
            checks=[check for child in child_results for check in child.checks],
        )

    def _resolve_variable(
        self,
        variable_name: str,
        facts: dict[str, Any],
        *,
        allow_special: bool = False,
    ) -> tuple[Any, list[str]]:
        """Resolve direct facts first, then derived variables, then mark missing."""

        self._ensure_allowed_variable(variable_name, allow_special=allow_special)
        if variable_name in facts:
            return facts[variable_name], []
        if variable_name in DERIVED_VARIABLES:
            return self._compute_derived_variable(variable_name, facts)
        return _MISSING, [variable_name]

    def _compute_derived_variable(
        self,
        variable_name: str,
        facts: dict[str, Any],
    ) -> tuple[Decimal | object, list[str]]:
        """Compute one supported derived variable from source facts on demand."""

        missing_variables = [
            required
            for required in ("ex_works", "non_originating")
            if facts.get(required) is None
        ]
        if missing_variables:
            return _MISSING, missing_variables

        ex_works = self._coerce_numeric_value(facts["ex_works"])
        non_originating = self._coerce_numeric_value(facts["non_originating"])
        if ex_works == Decimal("0"):
            raise ExpressionEvaluationError("Division by zero: ex_works is 0")

        if variable_name == "vnom_percent":
            return (non_originating / ex_works) * Decimal("100"), []
        if variable_name == "va_percent":
            return ((ex_works - non_originating) / ex_works) * Decimal("100"), []
        raise ExpressionEvaluationError(
            f"Unsupported derived variable '{variable_name}'",
            detail={"variable_name": variable_name},
        )

    def _ensure_allowed_variable(self, variable_name: str, *, allow_special: bool) -> None:
        """Reject variable names outside the contract-defined whitelist."""

        allowed_variables = ALLOWED_VARIABLES | (SPECIAL_VARIABLES if allow_special else set())
        if variable_name not in allowed_variables:
            raise ExpressionEvaluationError(
                f"Variable '{variable_name}' is not allowed in expressions",
                detail={"variable_name": variable_name},
            )

    @staticmethod
    def _assert_depth(depth: int) -> None:
        """Enforce the maximum expression tree depth."""

        if depth > MAX_EXPRESSION_DEPTH:
            raise ExpressionEvaluationError("Expression exceeds maximum depth of 10 levels")

    @staticmethod
    def _text_node_depth(node: ComparisonNode | LogicalNode) -> int:
        """Calculate parsed text-expression depth for safety bounds."""

        if isinstance(node, ComparisonNode):
            return 1
        return 1 + max(ExpressionEvaluator._text_node_depth(child) for child in node.operands)

    @staticmethod
    def _merge_missing(*missing_groups: list[str]) -> list[str]:
        """Merge missing variable names while preserving first-seen order."""

        merged: list[str] = []
        for group in missing_groups:
            for variable_name in group:
                if variable_name not in merged:
                    merged.append(variable_name)
        return merged

    @staticmethod
    def _format_value(value: Any) -> str:
        """Render a value in a stable, human-readable form."""

        if value is _MISSING:
            return "<missing>"
        if isinstance(value, bool):
            return str(value).lower()
        if isinstance(value, Decimal):
            text = format(value, "f")
            return text.rstrip("0").rstrip(".") if "." in text else text
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            text = format(Decimal(str(value)), "f")
            return text.rstrip("0").rstrip(".") if "." in text else text
        if isinstance(value, list):
            rendered = ", ".join(ExpressionEvaluator._format_value(item) for item in value)
            return f"[{rendered}]"
        return str(value)

    def _format_resolved_operand(self, operand: ResolvedOperand) -> str:
        """Render a variable or literal operand with substituted value when available."""

        if operand.is_variable:
            return f"{operand.source_name}({self._format_value(operand.value)})"
        return self._format_value(operand.value)

    def _observed_value(self, operand: ResolvedOperand) -> str:
        """Render the observed value stored in an AtomicCheck."""

        return self._format_value(operand.value)

    def _expected_value(self, operand: ResolvedOperand) -> str:
        """Render the expected value stored in an AtomicCheck."""

        if operand.is_variable:
            return self._format_resolved_operand(operand)
        return self._format_value(operand.value)

    def _compare_values(self, left: Any, operator: str, right: Any) -> bool:
        """Compare two resolved values using the supported operator set."""

        if operator in {"<=", ">=", "<", ">"}:
            left_number = self._coerce_numeric_value(left)
            right_number = self._coerce_numeric_value(right)
            if operator == "<=":
                return left_number <= right_number
            if operator == ">=":
                return left_number >= right_number
            if operator == "<":
                return left_number < right_number
            return left_number > right_number

        if self._is_numeric_value(left) and self._is_numeric_value(right):
            left = self._coerce_numeric_value(left)
            right = self._coerce_numeric_value(right)
        if operator == "==":
            return left == right
        if operator == "!=":
            return left != right
        raise ExpressionEvaluationError(
            f"Unsupported comparison operator '{operator}'",
            detail={"operator": operator},
        )

    @staticmethod
    def _is_numeric_value(value: Any) -> bool:
        """Return True for numeric comparison candidates except booleans."""

        return isinstance(value, (int, float, Decimal)) and not isinstance(value, bool)

    def _coerce_numeric_value(self, value: Any) -> Decimal:
        """Convert supported numeric values to Decimal for stable comparisons."""

        if not self._is_numeric_value(value):
            raise ExpressionEvaluationError(
                "Comparison requires numeric values",
                detail={"value": self._format_value(value)},
            )
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ExpressionEvaluationError(
                "Invalid numeric value in expression evaluation",
                detail={"value": str(value)},
            ) from exc

    def _ensure_numeric_literal(self, value: Any, *, field_name: str) -> None:
        """Validate numeric literal fields during JSON expression validation."""

        if not self._is_numeric_value(value):
            raise ExpressionEvaluationError(
                f"expression_json field '{field_name}' must be numeric",
                detail={"field_name": field_name, "value": value},
            )

    def _build_comparison_explanation(
        self,
        left_source: str,
        operator: str,
        right_source: str,
        passed: bool,
    ) -> str:
        """Return a concise explanation aligned with the failure-code conventions."""

        if passed:
            return f"Check passed: {left_source} {operator} {right_source}"

        failure_code = self._resolve_failure_code(left_source, operator, right_source)
        if failure_code is not None:
            return FAILURE_CODES[failure_code]
        return f"Check failed: {left_source} {operator} {right_source}"

    @staticmethod
    def _resolve_failure_code(
        left_source: str,
        operator: str,
        right_source: str,
    ) -> str | None:
        """Map common expression forms to canonical failure messages."""

        if left_source == "vnom_percent" and operator in {"<=", "<"}:
            return "FAIL_VNM_EXCEEDED"
        if left_source == "va_percent" and operator in {">=", ">"}:
            return "FAIL_VA_INSUFFICIENT"
        if left_source == "wholly_obtained" and operator == "==":
            return "FAIL_WO_NOT_MET"
        if left_source == "specific_process_performed" and operator == "==":
            return "FAIL_PROCESS_NOT_MET"
        if operator == "!=" and {left_source, right_source} == {
            "tariff_heading_input",
            "tariff_heading_output",
        }:
            return "FAIL_CTH_NOT_MET"
        if operator == "!=" and {left_source, right_source} == {
            "tariff_subheading_input",
            "tariff_subheading_output",
        }:
            return "FAIL_CTSH_NOT_MET"
        return None

    @staticmethod
    def _build_non_originating_explanation(test_op: str, passed: bool) -> str:
        """Explain heading or subheading shift checks using canonical wording."""

        if passed:
            if test_op == "heading_ne_output":
                return "All non-originating input headings differ from the output heading"
            return "All non-originating input subheadings differ from the output subheading"
        if test_op == "heading_ne_output":
            return FAILURE_CODES["FAIL_CTH_NOT_MET"]
        return FAILURE_CODES["FAIL_CTSH_NOT_MET"]
