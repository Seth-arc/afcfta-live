# Testing Rules

## Structure

- Unit tests: tests/unit/ (mock repositories, test service logic)
- Integration tests: tests/integration/ (real database, full pipeline)
- Fixtures: tests/fixtures/ (golden test cases — do not modify)

## Golden Test Cases

tests/fixtures/golden_cases.py is the acceptance criteria. Use these exact
inputs and expected outputs. Do not invent separate test data.

## What to Test

Expression evaluator: every rule type (WO, CTH, CTSH, VNM, VA, PROCESS),
missing facts, zero division, compound AND/OR.

Eligibility service: full 8-step orchestration, execution order, blocker
short-circuit behavior.

## Failure Assertions

- Assert specific failure_codes from app/core/failure_codes.py
- Assert exact missing_facts lists
- Assert confidence_class for provisional status cases

## Do Not

- Do not run tests in the sandbox — the human runs them
- Do not create test databases or run migrations — conftest.py handles this
