import { useCallback, useState } from "react";
import { postAssistantQuery, AisApiError } from "../api/client";
import type {
  AssessmentRequest,
  AssistantRequest,
  AssistantResponseEnvelope,
  ProductionFact,
} from "../api/types";

export type AssessmentStatus = "idle" | "loading" | "success" | "error";

export interface AssessmentState {
  status: AssessmentStatus;
  response: AssistantResponseEnvelope | null;
  error: {
    message: string;
    code: string | null;
    requestId: string | null;
    retryAfterSeconds: number | null;
  } | null;
}

const INITIAL_STATE: AssessmentState = {
  status: "idle",
  response: null,
  error: null,
};

function formatFactValue(fact: ProductionFact): string {
  if (fact.fact_value_text !== undefined) {
    return fact.fact_value_text;
  }
  if (fact.fact_value_number !== undefined) {
    return String(fact.fact_value_number);
  }
  if (fact.fact_value_boolean !== undefined) {
    return fact.fact_value_boolean ? "true" : "false";
  }
  return "unknown";
}

function buildAssistantRequest(request: AssessmentRequest): AssistantRequest {
  const factLines = request.production_facts
    .map((fact) => `- ${fact.fact_key}: ${formatFactValue(fact)}`)
    .join("\n");
  const existingDocuments =
    request.existing_documents && request.existing_documents.length > 0
      ? request.existing_documents.join(", ")
      : "none";

  return {
    user_input: [
      `Assess AfCFTA eligibility for HS6 ${request.hs6_code} from ${request.exporter} to ${request.importer} in ${request.year}.`,
      `Persona mode: ${request.persona_mode}.`,
      "Use these declared production facts exactly as written:",
      factLines || "- none",
      `Existing documents: ${existingDocuments}.`,
    ].join("\n"),
    context: {
      persona_mode: request.persona_mode,
      exporter: request.exporter,
      importer: request.importer,
      year: request.year,
    },
  };
}

export function useAssessment() {
  const [state, setState] = useState<AssessmentState>(INITIAL_STATE);

  const submit = useCallback(async (request: AssessmentRequest) => {
    setState({ status: "loading", response: null, error: null });

    try {
      const result = await postAssistantQuery(buildAssistantRequest(request));
      setState({
        status: "success",
        response: result.data,
        error: null,
      });
    } catch (err) {
      if (err instanceof AisApiError) {
        setState({
          status: "error",
          response: null,
          error: {
            message: err.message,
            code: err.code,
            requestId: err.requestId,
            retryAfterSeconds: err.retryAfterSeconds,
          },
        });
      } else {
        setState({
          status: "error",
          response: null,
          error: {
            message: "A network error occurred. Check your connection and try again.",
            code: null,
            requestId: null,
            retryAfterSeconds: null,
          },
        });
      }
    }
  }, []);

  const reset = useCallback(() => {
    setState(INITIAL_STATE);
  }, []);

  return { ...state, submit, reset };
}
