"""Domain enums aligned to the PostgreSQL contract and operational API enums."""

from __future__ import annotations

from enum import Enum


class AuthorityTierEnum(str, Enum):
    BINDING = "binding"
    OFFICIAL_OPERATIONAL = "official_operational"
    INTERPRETIVE = "interpretive"
    ANALYTIC_ENRICHMENT = "analytic_enrichment"


class SourceTypeEnum(str, Enum):
    AGREEMENT = "agreement"
    PROTOCOL = "protocol"
    ANNEX = "annex"
    APPENDIX = "appendix"
    TARIFF_SCHEDULE = "tariff_schedule"
    MINISTERIAL_DECISION = "ministerial_decision"
    STATUS_NOTICE = "status_notice"
    IMPLEMENTATION_CIRCULAR = "implementation_circular"
    GUIDANCE_NOTE = "guidance_note"
    MANUAL = "manual"
    ANALYTICS_REFERENCE = "analytics_reference"
    OTHER = "other"


class SourceStatusEnum(str, Enum):
    CURRENT = "current"
    SUPERSEDED = "superseded"
    PROVISIONAL = "provisional"
    DRAFT = "draft"
    PENDING = "pending"
    ARCHIVED = "archived"


class InstrumentTypeEnum(str, Enum):
    AGREEMENT = "agreement"
    PROTOCOL = "protocol"
    ANNEX = "annex"
    APPENDIX = "appendix"
    DECISION = "decision"
    CIRCULAR = "circular"
    GUIDANCE = "guidance"
    MANUAL = "manual"
    OTHER = "other"


class ProvisionStatusEnum(str, Enum):
    IN_FORCE = "in_force"
    PROVISIONAL = "provisional"
    PENDING = "pending"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"


class HsLevelEnum(str, Enum):
    CHAPTER = "chapter"
    HEADING = "heading"
    SUBHEADING = "subheading"
    TARIFF_LINE = "tariff_line"


class RuleStatusEnum(str, Enum):
    AGREED = "agreed"
    PENDING = "pending"
    PARTIALLY_AGREED = "partially_agreed"
    PROVISIONAL = "provisional"
    SUPERSEDED = "superseded"


class RuleComponentTypeEnum(str, Enum):
    WO = "WO"
    VA = "VA"
    VNM = "VNM"
    CTH = "CTH"
    CTSH = "CTSH"
    CC = "CC"
    PROCESS = "PROCESS"
    ALT_RULE = "ALT_RULE"
    EXCEPTION = "EXCEPTION"
    NOTE = "NOTE"


class OperatorTypeEnum(str, Enum):
    AND = "and"
    OR = "or"
    NOT = "not"
    STANDALONE = "standalone"


class ThresholdBasisEnum(str, Enum):
    EX_WORKS = "ex_works"
    FOB = "fob"
    VALUE_OF_NON_ORIGINATING_MATERIALS = "value_of_non_originating_materials"
    CUSTOMS_VALUE = "customs_value"
    UNKNOWN = "unknown"


class ScheduleStatusEnum(str, Enum):
    OFFICIAL = "official"
    PROVISIONAL = "provisional"
    GAZETTED = "gazetted"
    SUPERSEDED = "superseded"
    DRAFT = "draft"


class TariffCategoryEnum(str, Enum):
    LIBERALISED = "liberalised"
    SENSITIVE = "sensitive"
    EXCLUDED = "excluded"
    UNKNOWN = "unknown"


class StagingTypeEnum(str, Enum):
    IMMEDIATE = "immediate"
    LINEAR = "linear"
    STEPWISE = "stepwise"
    UNKNOWN = "unknown"


class RateStatusEnum(str, Enum):
    IN_FORCE = "in_force"
    PROJECTED = "projected"
    PROVISIONAL = "provisional"
    SUPERSEDED = "superseded"


class StatusTypeEnum(str, Enum):
    AGREED = "agreed"
    PENDING = "pending"
    PROVISIONAL = "provisional"
    UNDER_REVIEW = "under_review"
    TRANSITIONAL = "transitional"
    SUPERSEDED = "superseded"
    IN_FORCE = "in_force"
    NOT_YET_OPERATIONAL = "not_yet_operational"
    EXPIRED = "expired"


class PersonaModeEnum(str, Enum):
    OFFICER = "officer"
    ANALYST = "analyst"
    EXPORTER = "exporter"
    SYSTEM = "system"


class RequirementTypeEnum(str, Enum):
    CERTIFICATE_OF_ORIGIN = "certificate_of_origin"
    SUPPLIER_DECLARATION = "supplier_declaration"
    PROCESS_RECORD = "process_record"
    BILL_OF_MATERIALS = "bill_of_materials"
    COST_BREAKDOWN = "cost_breakdown"
    INVOICE = "invoice"
    TRANSPORT_RECORD = "transport_record"
    CUSTOMS_SUPPORTING_DOC = "customs_supporting_doc"
    VALUATION_SUPPORT = "valuation_support"
    INSPECTION_RECORD = "inspection_record"
    OTHER = "other"


class DecisionOutcomeEnum(str, Enum):
    LIKELY_ELIGIBLE = "likely_eligible"
    LIKELY_NOT_ELIGIBLE = "likely_not_eligible"
    UNCERTAIN = "uncertain"
    INSUFFICIENT_INFORMATION = "insufficient_information"


class ConfidenceLevelEnum(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CaseSubmissionStatusEnum(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    CLOSED = "closed"
    ARCHIVED = "archived"


class FactSourceTypeEnum(str, Enum):
    USER_INPUT = "user_input"
    DOCUMENT_UPLOAD = "document_upload"
    SYSTEM_INFERRED = "system_inferred"
    OFFICER_NOTE = "officer_note"
    EXTERNAL_DATA = "external_data"


class FactValueTypeEnum(str, Enum):
    TEXT = "text"
    NUMBER = "number"
    BOOLEAN = "boolean"
    DATE = "date"
    JSON = "json"
    LIST = "list"


class VerificationRiskCategoryEnum(str, Enum):
    ORIGIN_CLAIM = "origin_claim"
    DOCUMENTARY_GAP = "documentary_gap"
    VALUATION_RISK = "valuation_risk"
    CUMULATION_RISK = "cumulation_risk"
    PROCESS_RISK = "process_risk"
    TARIFF_CLASSIFICATION_RISK = "tariff_classification_risk"
    SCHEDULE_STATUS_RISK = "schedule_status_risk"
    GENERAL = "general"


class ChangeTypeEnum(str, Enum):
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    STATUS_CHANGED = "status_changed"
    SUPERSEDED = "superseded"
    EFFECTIVE_DATE_CHANGED = "effective_date_changed"
    STRUCTURE_CHANGED = "structure_changed"
    VALUE_CHANGED = "value_changed"


class FailureTypeEnum(str, Enum):
    RULE_NOT_MET = "rule_not_met"
    THRESHOLD_NOT_MET = "threshold_not_met"
    TARIFF_SHIFT_NOT_MET = "tariff_shift_not_met"
    SPECIFIC_PROCESS_NOT_MET = "specific_process_not_met"
    MISSING_DOCUMENT = "missing_document"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    CUMULATION_NOT_SUPPORTED = "cumulation_not_supported"
    VALUATION_NOT_SUPPORTED = "valuation_not_supported"
    CLASSIFICATION_UNCERTAIN = "classification_uncertain"
    SCHEDULE_NOT_OPERATIONAL = "schedule_not_operational"
    STATUS_PENDING = "status_pending"
    STATUS_PROVISIONAL = "status_provisional"
    DATA_GAP = "data_gap"
    OTHER = "other"


class SeverityEnum(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CounterfactualTypeEnum(str, Enum):
    SOURCING_CHANGE = "sourcing_change"
    VALUE_ADJUSTMENT = "value_adjustment"
    PROCESS_CHANGE = "process_change"
    DOCUMENTATION_ADDITION = "documentation_addition"
    CUMULATION_CHANGE = "cumulation_change"
    CLASSIFICATION_REVIEW = "classification_review"
    CORRIDOR_CHANGE = "corridor_change"
    TIMING_CHANGE = "timing_change"
    OTHER = "other"


class ProjectedOutcomeEnum(str, Enum):
    LIKELY_ELIGIBLE = "likely_eligible"
    LIKELY_NOT_ELIGIBLE = "likely_not_eligible"
    STILL_UNCERTAIN = "still_uncertain"
    REQUIRES_MORE_EVIDENCE = "requires_more_evidence"


class AlertTypeEnum(str, Enum):
    RULE_STATUS_CHANGED = "rule_status_changed"
    SCHEDULE_UPDATED = "schedule_updated"
    RATE_CHANGED = "rate_changed"
    PROVISION_UPDATED = "provision_updated"
    TRANSITION_EXPIRING = "transition_expiring"
    DOCUMENT_REQUIREMENT_CHANGED = "document_requirement_changed"
    CORRIDOR_RISK_CHANGED = "corridor_risk_changed"
    CASE_REVIEW_NEEDED = "case_review_needed"
    DATA_QUALITY_ISSUE = "data_quality_issue"
    OTHER = "other"


class AlertSeverityEnum(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AlertStatusEnum(str, Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class CorridorStatusEnum(str, Enum):
    OPERATIONAL = "operational"
    PARTIALLY_OPERATIONAL = "partially_operational"
    PROVISIONAL = "provisional"
    NOT_YET_OPERATIONAL = "not_yet_operational"
    UNKNOWN = "unknown"


class PersonaMode(str, Enum):
    OFFICER = "officer"
    ANALYST = "analyst"
    EXPORTER = "exporter"
    SYSTEM = "system"


class LegalOutcome(str, Enum):
    ELIGIBLE = "eligible"
    NOT_ELIGIBLE = "not_eligible"
    UNCERTAIN = "uncertain"
    NOT_YET_OPERATIONAL = "not_yet_operational"
    INSUFFICIENT_INFORMATION = "insufficient_information"


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CheckSeverity(str, Enum):
    BLOCKER = "blocker"
    MAJOR = "major"
    MINOR = "minor"
    INFO = "info"


class CheckGroup(str, Enum):
    STATUS = "status"
    RULE = "rule"
    PROCEDURE = "procedure"
    EVIDENCE = "evidence"
    CORRIDOR = "corridor"


class ScheduleStatus(str, Enum):
    OFFICIAL = "official"
    PROVISIONAL = "provisional"
    GAZETTED = "gazetted"
    SUPERSEDED = "superseded"
    DRAFT = "draft"
