/**
 * Error handling for AIS API responses.
 *
 * Maps HTTP status codes and AIS domain error codes to user-facing messages.
 * Source of truth: docs/api/error-codes.md
 */

import type { ApiErrorResponse } from "./types";

// ---------------------------------------------------------------------------
// Typed API error
// ---------------------------------------------------------------------------

export class AisApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly detail: Record<string, unknown> | undefined;
  readonly requestId: string | null;
  readonly retryAfterSeconds: number | null;

  constructor(
    status: number,
    code: string,
    message: string,
    detail?: Record<string, unknown>,
    requestId?: string | null,
    retryAfterSeconds?: number | null,
  ) {
    super(message);
    this.name = "AisApiError";
    this.status = status;
    this.code = code;
    this.detail = detail;
    this.requestId = requestId ?? null;
    this.retryAfterSeconds = retryAfterSeconds ?? null;
  }
}

// ---------------------------------------------------------------------------
// Domain error code → user-facing message
// ---------------------------------------------------------------------------

const USER_MESSAGES: Record<string, string> = {
  AIS_ERROR: "Something went wrong processing your request. Please try again.",
  CLASSIFICATION_ERROR:
    "The product code could not be resolved. Check that you entered at least 6 digits and the correct HS version.",
  RULE_NOT_FOUND:
    "No rule of origin exists for this product code. This may be a legal-data gap rather than a clear pass.",
  TARIFF_NOT_FOUND:
    "No tariff schedule was found for this corridor and product. Verify the exporter, importer, and year.",
  STATUS_UNKNOWN:
    "No status data exists for the requested entity. Recheck the entity key and whether status data has been loaded.",
  AUDIT_TRAIL_NOT_FOUND:
    "No audit trail was found. Confirm the case or evaluation ID and that audit persistence was enabled.",
  CORRIDOR_NOT_SUPPORTED:
    "This trade corridor is not supported in the current release. Supported countries: NGA, GHA, CIV, SEN, CMR.",
  INSUFFICIENT_FACTS:
    "Not enough production facts were provided for a deterministic evaluation. Supply the missing facts and retry.",
  EXPRESSION_EVALUATION_ERROR:
    "A server-side error occurred evaluating the rule expression. Please report this issue.",
  INTERNAL_ERROR:
    "An unexpected server error occurred. Please try again later or contact support.",
};

export function userMessageForCode(code: string): string {
  return USER_MESSAGES[code] ?? `An error occurred (${code}). Please try again.`;
}

// ---------------------------------------------------------------------------
// HTTP status → fallback user message (when body parsing fails)
// ---------------------------------------------------------------------------

export function userMessageForStatus(status: number): string {
  if (status === 400) return "The request was invalid. Please check your input.";
  if (status === 401) return "Authentication required. Please check your API key.";
  if (status === 403) return "Access denied.";
  if (status === 404) return "The requested resource was not found.";
  if (status === 422) return "The request could not be processed. Please check your input.";
  if (status >= 500) return "A server error occurred. Please try again later.";
  return `Unexpected error (HTTP ${status}).`;
}

// ---------------------------------------------------------------------------
// Response parser — turns a non-ok Response into a typed AisApiError
// ---------------------------------------------------------------------------

function parseRetryAfter(response: Response): number | null {
  const raw = response.headers.get("Retry-After");
  if (!raw) return null;
  const seconds = Number(raw);
  return Number.isFinite(seconds) && seconds > 0 ? seconds : null;
}

export async function parseErrorResponse(response: Response): Promise<AisApiError> {
  const retryAfter = parseRetryAfter(response);

  if (response.status === 429) {
    const msg = retryAfter
      ? `Too many requests. Please wait ${retryAfter} seconds before trying again.`
      : "Too many requests. Please wait a moment before trying again.";
    return new AisApiError(429, "RATE_LIMITED", msg, undefined, null, retryAfter);
  }

  let body: ApiErrorResponse | undefined;
  try {
    body = (await response.json()) as ApiErrorResponse;
  } catch {
    return new AisApiError(
      response.status,
      "UNKNOWN",
      userMessageForStatus(response.status),
    );
  }

  if (body?.error) {
    return new AisApiError(
      response.status,
      body.error.code,
      userMessageForCode(body.error.code),
      body.error.details,
      body.meta?.request_id ?? null,
      retryAfter,
    );
  }

  return new AisApiError(
    response.status,
    "UNKNOWN",
    userMessageForStatus(response.status),
  );
}
