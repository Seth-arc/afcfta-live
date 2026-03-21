"""Canonical failure codes for the eligibility engine."""

FAILURE_CODES = {
    # Blocker-level
    "UNKNOWN_HS6": "HS6 code could not be resolved",
    "NO_PSR_FOUND": "No applicable PSR rule found for this HS6",
    "NO_SCHEDULE": "No tariff schedule found for this corridor",
    "NOT_OPERATIONAL": "Corridor or instrument not yet operational",
    "MISSING_CORE_FACTS": "Required production facts are missing",
    # PSR failures
    "FAIL_CTH_NOT_MET": "Change in tariff heading not demonstrated",
    "FAIL_CTSH_NOT_MET": "Change in tariff subheading not demonstrated",
    "FAIL_VNM_EXCEEDED": "Value of non-originating materials exceeds threshold",
    "FAIL_VA_INSUFFICIENT": "Value added percentage below threshold",
    "FAIL_WO_NOT_MET": "Product is not wholly obtained",
    "FAIL_PROCESS_NOT_MET": "Required specific process not performed",
    # General rule failures
    "FAIL_INSUFFICIENT_OPERATIONS": "Only insufficient/minimal operations performed",
    "FAIL_DIRECT_TRANSPORT": "Direct transport requirement not met",
    "FAIL_CUMULATION_INVALID": "Cumulation conditions not satisfied",
    # Status constraints
    "RULE_STATUS_PENDING": "PSR rule status is pending — not yet enforceable",
    "RULE_STATUS_PROVISIONAL": "PSR rule is provisional",
    "SCHEDULE_PROVISIONAL": "Tariff schedule is provisional",
    "SCHEDULE_NOT_GAZETTED": "Tariff schedule not yet gazetted",
}