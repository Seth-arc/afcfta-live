/**
 * AIS API client.
 *
 * - Forwards X-API-Key from configuration.
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
  apiKey: string;
}

let _config: ApiClientConfig = {
  baseUrl: "",
  apiKey: "",
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

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<ApiResponse<T>> {
  const url = `${_config.baseUrl}${path}`;

  const apiKey = _config.apiKey || "dev-local-key";

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Request-ID": generateRequestId(),
    "X-API-Key": apiKey,
  };

  console.debug("[AIS client]", method, path, "apiKey present:", !!apiKey);

  const response = await fetch(url, {
    method,
    headers,
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
 * POST /api/v1/assessments
 * Runs the full deterministic eligibility engine.
 */
export async function postAssessment(
  assessmentRequest: AssessmentRequest,
): Promise<ApiResponse<EligibilityAssessmentResponse>> {
  return request<EligibilityAssessmentResponse>(
    "POST",
    "/api/v1/assessments",
    assessmentRequest,
  );
}

/**
 * POST /api/v1/assistant
 * Submits a natural-language query to the NIM assistant.
 */
export async function postAssistantQuery(
  assistantRequest: AssistantRequest,
): Promise<ApiResponse<AssistantResponseEnvelope>> {
  return request<AssistantResponseEnvelope>(
    "POST",
    "/api/v1/assistant/assess",
    assistantRequest,
  );
}

/**
 * GET /api/v1/audit/evaluations/{evaluationId}
 * Reconstructs the stored decision trace for one persisted evaluation.
 */
export async function getAuditTrail(
  evaluationId: string,
): Promise<ApiResponse<unknown>> {
  return request<unknown>("GET", `/api/v1/audit/evaluations/${encodeURIComponent(evaluationId)}`);
}

/**
 * GET /api/v1/rules/{hs6Code}
 * Resolves the governing product-specific rule bundle for a product.
 */
export async function getRules(
  hs6Code: string,
  hsVersion?: string,
): Promise<ApiResponse<unknown>> {
  const params = new URLSearchParams();
  if (hsVersion) params.set("hs_version", hsVersion);
  const qs = params.toString();
  return request<unknown>("GET", `/api/v1/rules/${encodeURIComponent(hs6Code)}${qs ? `?${qs}` : ""}`);
}

/**
 * GET /api/v1/tariffs
 * Returns the tariff outcome for a corridor, HS6 code, and year.
 */
export async function getTariffs(params: {
  exporter: string;
  importer: string;
  hs6: string;
  year: number;
  hs_version?: string;
}): Promise<ApiResponse<unknown>> {
  const searchParams = new URLSearchParams({
    exporter: params.exporter,
    importer: params.importer,
    hs6: params.hs6,
    year: String(params.year),
  });
  if (params.hs_version) searchParams.set("hs_version", params.hs_version);
  return request<unknown>("GET", `/api/v1/tariffs?${searchParams.toString()}`);
}

export { AisApiError };
