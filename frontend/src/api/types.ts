/**
 * TypeScript types mirroring the AIS backend contracts exactly.
 *
 * Sources of truth:
 *   - app/schemas/assessments.py          (EligibilityAssessmentResponse, TariffOutcomeResponse)
 *   - app/schemas/nim/assistant.py        (AssistantResponseEnvelope, ClarificationResponse, AssistantRendering, AssistantError)
 *   - tests/contract_constants.py         (frozen field sets)
 *   - docs/api/endpoints.md              (request/response shapes)
 *   - docs/api/error-codes.md            (error codes)
 */

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export type ResponseType = "clarification" | "assessment" | "error";

export type ConfidenceClass = "complete" | "provisional" | "incomplete";

export type PersonaMode = "exporter" | "officer" | "analyst" | "system";

// ---------------------------------------------------------------------------
// Nested types
// ---------------------------------------------------------------------------

/** Matches TariffOutcomeResponse + TARIFF_OUTCOME_FIELDS */
export interface TariffOutcome {
  preferential_rate: string | null;
  base_rate: string | null;
  status: string;
  provenance_ids: string[];
}

/** Matches EligibilityAssessmentResponse + ELIGIBILITY_ASSESSMENT_RESPONSE_FIELDS */
export interface EligibilityAssessmentResponse {
  hs6_code: string;
  eligible: boolean;
  pathway_used: string | null;
  rule_status: string;
  tariff_outcome: TariffOutcome | null;
  failures: string[];
  missing_facts: string[];
  evidence_required: string[];
  missing_evidence: string[];
  readiness_score: number | null;
  completeness_ratio: number | null;
  confidence_class: ConfidenceClass;
  audit_persisted: boolean;
}

/** Matches AssistantRendering + ASSISTANT_RENDERING_FIELDS */
export interface AssistantRendering {
  headline: string;
  summary: string;
  gap_analysis: string | null;
  fix_strategy: string | null;
  next_steps: string[];
  warnings: string[];
}

/** Matches ClarificationResponse + CLARIFICATION_FIELDS */
export interface ClarificationResponse {
  question: string;
  missing_facts: string[];
  missing_evidence: string[];
}

/** Matches AssistantError + ASSISTANT_ERROR_FIELDS */
export interface AssistantError {
  code: string;
  message: string;
  detail: Record<string, unknown> | null;
}

// ---------------------------------------------------------------------------
// Envelope
// ---------------------------------------------------------------------------

/** Matches AssistantResponseEnvelope + ASSISTANT_RESPONSE_ENVELOPE_FIELDS */
export interface AssistantResponseEnvelope {
  response_type: ResponseType;
  case_id: string | null;
  evaluation_id: string | null;
  audit_url: string | null;
  audit_persisted: boolean;
  assessment: EligibilityAssessmentResponse | null;
  clarification: ClarificationResponse | null;
  explanation: string | null;
  explanation_fallback_used: boolean;
  assistant_rendering: AssistantRendering | null;
  error: AssistantError | null;
}

// ---------------------------------------------------------------------------
// Request types
// ---------------------------------------------------------------------------

export interface AssistantContext {
  persona_mode?: PersonaMode;
  exporter?: string;
  importer?: string;
  year?: number;
}

export interface AssistantRequest {
  user_input: string;
  context?: AssistantContext;
}

export interface ProductionFact {
  fact_type: string;
  fact_key: string;
  fact_value_type: "text" | "number" | "boolean";
  fact_value_text?: string;
  fact_value_number?: number;
  fact_value_boolean?: boolean;
}

export interface AssessmentRequest {
  hs6_code: string;
  hs_version?: string;
  exporter: string;
  importer: string;
  year: number;
  persona_mode: PersonaMode;
  production_facts: ProductionFact[];
  existing_documents?: string[];
  case_id?: string;
}

// ---------------------------------------------------------------------------
// API-level error envelope (shared across all endpoints)
// ---------------------------------------------------------------------------

export interface ApiErrorDetail {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export interface ApiErrorResponse {
  error: ApiErrorDetail;
  meta: {
    request_id: string;
    timestamp: string;
  };
}

// ---------------------------------------------------------------------------
// Replay headers captured from assessment responses
// ---------------------------------------------------------------------------

export interface ReplayHeaders {
  caseId: string | null;
  evaluationId: string | null;
  auditUrl: string | null;
}
