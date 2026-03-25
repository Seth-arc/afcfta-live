"""NIM orchestration services.

This package contains the thin NIM layer that sits on top of the deterministic
engine. It never owns eligibility logic, evidence rules, or audit persistence.

Services in this package:
- intake_service   — parse natural-language input into a NimAssessmentDraft
- clarification_service — generate a focused follow-up question from engine gaps
- explanation_service  — wrap a deterministic result in plain-language text
- client           — HTTP wrapper for the NIM model API

What intentionally lives OUTSIDE this package:
- eligibility_service  — owns all eligibility logic and engine orchestration
- evidence_service     — owns evidence requirement lookup and readiness scoring
- audit_service        — owns evaluation persistence and replay reconstruction
- All repositories     — NIM services never touch the database directly
"""
