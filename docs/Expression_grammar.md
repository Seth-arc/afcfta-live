# Expression Grammar for the AfCFTA Eligibility Engine

This document defines the two expression formats used in the system and the
rules the expression evaluator must follow. It is the specification for
`app/services/expression_evaluator.py`.

---

## 1. Where Expressions Live

Expressions appear in two places in the database:

| Column | Table | Format | Purpose |
|--------|-------|--------|---------|
| `normalized_expression` | `psr_rule_component` | Text (simple) | Human-readable, one condition |
| `expression_json` | `eligibility_rule_pathway` | JSON (tree) | Machine-executable, full pathway |

The expression evaluator must support both. `normalized_expression` is used
for display and simple evaluation. `expression_json` is used for the
deterministic engine pipeline.

---

## 2. Simple Text Expression Format

Used in `psr_rule_component.normalized_expression`. One condition per string.

### Threshold comparison

```
vnom_percent <= 60
va_percent >= 40
vnom_percent <= 50 AND specific_process_performed == true
```

### Boolean fact check

```
wholly_obtained == true
specific_process_performed == true
cumulation_claimed == false
```

### Tariff shift check

```
tariff_heading_input != tariff_heading_output
tariff_subheading_input != tariff_subheading_output
```

### Compound expressions

```
vnom_percent <= 60 AND specific_process_performed == true
wholly_obtained == true OR tariff_heading_input != tariff_heading_output
```

### Operators

| Type | Operators |
|------|-----------|
| Comparison | `<=`, `>=`, `<`, `>`, `==`, `!=` |
| Logical | `AND`, `OR` (case-insensitive) |

No parentheses in v0.1. Flatten complex logic into separate pathways instead.

---

## 3. JSON Expression Tree Format

Used in `eligibility_rule_pathway.expression_json`. This is the primary format
for the deterministic engine.

### Structure

Every node has an `op` field. Nodes are composed recursively.

### Combinators

**`all`** — AND logic. All children must pass.

```json
{
  "op": "all",
  "args": [
    { "op": "formula_lte", "formula": "vnom_percent", "value": 60 },
    { "op": "fact_eq", "fact": "specific_process_performed", "value": true }
  ]
}
```

**`any`** — OR logic. At least one child must pass.

```json
{
  "op": "any",
  "args": [
    { "op": "fact_eq", "fact": "wholly_obtained", "value": true },
    { "op": "formula_lte", "formula": "vnom_percent", "value": 50 }
  ]
}
```

### Leaf Nodes

**`formula_lte`** — Derived variable must be less than or equal to threshold.

```json
{ "op": "formula_lte", "formula": "vnom_percent", "value": 60 }
```

**`formula_gte`** — Derived variable must be greater than or equal to threshold.

```json
{ "op": "formula_gte", "formula": "va_percent", "value": 40 }
```

**`fact_eq`** — A case fact must equal a specific value.

```json
{ "op": "fact_eq", "fact": "wholly_obtained", "value": true }
```

**`fact_ne`** — A case fact must NOT equal a specific value.

```json
{ "op": "fact_ne", "fact": "tariff_heading_input", "ref_fact": "tariff_heading_output" }
```

When `ref_fact` is present instead of `value`, the evaluator compares two facts
against each other (used for tariff shift checks).

**`every_non_originating_input`** — All non-originating material inputs must
satisfy a condition. Used for CTH/CTSH where every input material's HS code
must differ from the output product's HS code.

```json
{
  "op": "every_non_originating_input",
  "test": {
    "op": "heading_ne_output"
  }
}
```

Test operations:
- `heading_ne_output` — input HS heading (4-digit) differs from output heading (CTH)
- `subheading_ne_output` — input HS subheading (6-digit) differs from output subheading (CTSH)

This requires the facts dict to contain:
- `non_originating_inputs`: list of `{"hs4_code": "...", "hs6_code": "..."}`
- `output_hs6_code`: the HS6 of the product being exported

---

## 4. Complete Pathway Examples

### WO (Wholly Obtained)

```json
{
  "pathway_code": "WO",
  "expression": {
    "op": "fact_eq",
    "fact": "wholly_obtained",
    "value": true
  }
}
```

### CTH (Change in Tariff Heading)

```json
{
  "pathway_code": "CTH",
  "expression": {
    "op": "every_non_originating_input",
    "test": { "op": "heading_ne_output" }
  }
}
```

Simplified form when facts provide heading directly:

```json
{
  "pathway_code": "CTH",
  "expression": {
    "op": "fact_ne",
    "fact": "tariff_heading_input",
    "ref_fact": "tariff_heading_output"
  }
}
```

### VNM (Value of Non-Originating Materials)

```json
{
  "pathway_code": "VNM",
  "expression": {
    "op": "formula_lte",
    "formula": "vnom_percent",
    "value": 60
  }
}
```

### VA (Value Added)

```json
{
  "pathway_code": "VA",
  "expression": {
    "op": "formula_gte",
    "formula": "va_percent",
    "value": 40
  }
}
```

### PROCESS (Specific Process)

```json
{
  "pathway_code": "PROCESS",
  "expression": {
    "op": "fact_eq",
    "fact": "specific_process_performed",
    "value": true
  }
}
```

### CTH + VNM compound (AND)

```json
{
  "pathway_code": "CTH_VNM",
  "expression": {
    "op": "all",
    "args": [
      {
        "op": "fact_ne",
        "fact": "tariff_heading_input",
        "ref_fact": "tariff_heading_output"
      },
      {
        "op": "formula_lte",
        "formula": "vnom_percent",
        "value": 50
      }
    ]
  }
}
```

### Alternative pathways (OR at pathway level)

OR logic is NOT represented inside a single expression tree. Instead, the
`eligibility_rule_pathway` table stores multiple rows for the same `psr_id`,
each with its own `expression_json` and `priority_rank`. The eligibility
service tries them in priority_rank order. First pass wins.

Example: A product qualifies via CTH **or** VNM ≤ 60%.

Row 1: `priority_rank=1`, `pathway_code="CTH"`, `expression_json={CTH tree}`
Row 2: `priority_rank=2`, `pathway_code="VNM"`, `expression_json={VNM tree}`

The evaluator tries CTH first. If it passes, done. If it fails, try VNM.

---

## 5. Variable Resolution

When the evaluator encounters a variable name, it resolves in this order:

1. **Direct fact lookup** — check the facts dict for the variable name
2. **Derived variable computation** — if the variable is a known derived
   variable, compute it from source facts
3. **Missing** — if still unresolved, add to `missing_variables` and return
   None for that expression

### Derived Variable Formulas

```
vnom_percent = non_originating / ex_works * 100
va_percent   = (ex_works - non_originating) / ex_works * 100
```

Both require:
- `ex_works` present and > 0
- `non_originating` present

If `ex_works` is 0 → this is an **error**, not a silent default. Raise
`ExpressionEvaluationError("Division by zero: ex_works is 0")`.

If `ex_works` or `non_originating` is missing → do not compute the derived
variable. Add the missing source fact(s) to `missing_variables`.

### Required Facts Per Rule Type

| Rule Type | Required Facts |
|-----------|----------------|
| WO | `wholly_obtained` |
| CTH | `tariff_heading_input`, `tariff_heading_output` (or `non_originating_inputs` + `output_hs6_code`) |
| CTSH | `tariff_subheading_input`, `tariff_subheading_output` (or `non_originating_inputs` + `output_hs6_code`) |
| VNM | `ex_works`, `non_originating` |
| VA | `ex_works`, `non_originating` |
| PROCESS | `specific_process_performed` |

See `app/core/fact_keys.py` for the full registry.

---

## 6. Evaluator Output

The expression evaluator returns three things for every evaluation:

```python
@dataclass
class ExpressionResult:
    result: Optional[bool]       # True = pass, False = fail, None = cannot evaluate
    evaluated_expression: str    # Human-readable with values substituted
    missing_variables: list[str] # Facts needed but not provided
```

For compound expressions, each leaf node produces its own check result. The
evaluator returns the overall result PLUS a list of atomic check results for
audit persistence:

```python
@dataclass
class AtomicCheck:
    check_code: str              # e.g., "FORMULA_LTE", "FACT_EQ", "HEADING_NE"
    passed: Optional[bool]
    expected_value: str
    observed_value: str
    explanation: str
```

These atomic checks are stored in `eligibility_check_result` for audit trail.

---

## 7. Safety Constraints

The expression evaluator is the most security-sensitive component in the system.

### MUST

- Parse expressions using a safe, purpose-built parser
- Whitelist allowed operations: the op types listed above and nothing else
- Whitelist allowed variable names: only those in `app/core/fact_keys.py`
  plus the derived variables
- Validate `expression_json` structure before evaluation (op field exists,
  args are lists, values are numbers/strings/booleans)
- Cap expression depth at 10 levels (prevent stack overflow)
- Cap expression text length at 500 characters

### MUST NOT

- Use Python's `eval()`, `exec()`, or `compile()`
- Allow function calls in expressions
- Allow attribute access (no `obj.attr`)
- Allow imports or module references
- Evaluate expressions from untrusted input without validation
- Silently default missing variables to any value (including 0, False, or "")

---

## 8. JSON Schema for expression_json

For validation in the pipeline and at API boundaries:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "PathwayExpression",
  "oneOf": [
    {
      "type": "object",
      "properties": {
        "op": { "enum": ["all", "any"] },
        "args": {
          "type": "array",
          "items": { "$ref": "#" },
          "minItems": 1
        }
      },
      "required": ["op", "args"]
    },
    {
      "type": "object",
      "properties": {
        "op": { "enum": ["formula_lte", "formula_gte"] },
        "formula": { "type": "string" },
        "value": { "type": "number" }
      },
      "required": ["op", "formula", "value"]
    },
    {
      "type": "object",
      "properties": {
        "op": { "enum": ["fact_eq"] },
        "fact": { "type": "string" },
        "value": {}
      },
      "required": ["op", "fact", "value"]
    },
    {
      "type": "object",
      "properties": {
        "op": { "enum": ["fact_ne"] },
        "fact": { "type": "string" }
      },
      "required": ["op", "fact"],
      "oneOf": [
        { "required": ["value"] },
        { "required": ["ref_fact"] }
      ]
    },
    {
      "type": "object",
      "properties": {
        "op": { "enum": ["every_non_originating_input"] },
        "test": {
          "type": "object",
          "properties": {
            "op": { "enum": ["heading_ne_output", "subheading_ne_output"] }
          },
          "required": ["op"]
        }
      },
      "required": ["op", "test"]
    }
  ]
}
```