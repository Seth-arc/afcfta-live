/**
 * Browser-safe AIS API client.
 *
 * - Uses the same-origin `/web/api/` boundary only.
 * - Captures X-AIS-Case-Id, X-AIS-Evaluation-Id, X-AIS-Audit-URL response headers.
 * - Sends X-Request-ID on every request for tracing.
 * - Parses error responses into typed AisApiError objects.
 */

import type {
  AssessmentRequest,
  AssistantRequest,
  AssistantResponseEnvelope,
  EligibilityAssessmentResponse,
  ReplayHeaders,
} from "./types";
import { AisApiError, parseErrorResponse } from "./errors";

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

export interface ApiClientConfig {
  baseUrl: string;
}

let _config: ApiClientConfig = {
  baseUrl: "/web/api",
};

export function configureApiClient(config: ApiClientConfig): void {
  _config = { ...config };
}

// ---------------------------------------------------------------------------
// Request ID generation
// ---------------------------------------------------------------------------

function generateRequestId(): string {
  return crypto.randomUUID();
}

// ---------------------------------------------------------------------------
// Core fetch wrapper
// ---------------------------------------------------------------------------

interface ApiResponse<T> {
  data: T;
  replayHeaders: ReplayHeaders;
}

function resolveUrl(path: string): string {
  const baseUrl = _config.baseUrl.replace(/\/+$/, "");
  return `${baseUrl}${path}`;
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<ApiResponse<T>> {
  const url = resolveUrl(path);

  const headers: Record<string, string> = {
    "X-Request-ID": generateRequestId(),
  };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(url, {
    method,
    headers,
    credentials: "same-origin",
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    throw await parseErrorResponse(response);
  }

  const data = (await response.json()) as T;

  const replayHeaders: ReplayHeaders = {
    caseId: response.headers.get("X-AIS-Case-Id"),
    evaluationId: response.headers.get("X-AIS-Evaluation-Id"),
    auditUrl: response.headers.get("X-AIS-Audit-URL"),
  };

  return { data, replayHeaders };
}

// ---------------------------------------------------------------------------
// Public API methods
// ---------------------------------------------------------------------------

/**
 * POST /web/api/assessments
 * Runs the full deterministic eligibility engine.
 */
export async function postAssessment(
  assessmentRequest: AssessmentRequest,
): Promise<ApiResponse<EligibilityAssessmentResponse>> {
  return request<EligibilityAssessmentResponse>(
    "POST",
    "/assessments",
    assessmentRequest,
  );
}

/**
 * POST /web/api/assistant/assess
 * Submits a natural-language query to the NIM assistant.
 */
export async function postAssistantQuery(
  assistantRequest: AssistantRequest,
): Promise<ApiResponse<AssistantResponseEnvelope>> {
  return request<AssistantResponseEnvelope>(
    "POST",
    "/assistant/assess",
    assistantRequest,
  );
}

/**
 * GET /web/api/audit/evaluations/{evaluationId}
 * Reconstructs the stored decision trace for one persisted evaluation.
 */
export async function getAuditTrail(
  evaluationId: string,
): Promise<ApiResponse<unknown>> {
  return request<unknown>(
    "GET",
    `/audit/evaluations/${encodeURIComponent(evaluationId)}`,
  );
}

export { AisApiError };
