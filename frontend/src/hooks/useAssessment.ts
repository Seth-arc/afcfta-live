import { useCallback, useState } from "react";
import { postAssessment, AisApiError } from "../api/client";
import type {
  AssessmentRequest,
  EligibilityAssessmentResponse,
  ReplayHeaders,
} from "../api/types";

export type AssessmentStatus = "idle" | "loading" | "success" | "error";

export interface AssessmentState {
  status: AssessmentStatus;
  response: EligibilityAssessmentResponse | null;
  replayHeaders: ReplayHeaders | null;
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
  replayHeaders: null,
  error: null,
};

export function useAssessment() {
  const [state, setState] = useState<AssessmentState>(INITIAL_STATE);

  const submit = useCallback(async (request: AssessmentRequest) => {
    setState({ status: "loading", response: null, replayHeaders: null, error: null });

    try {
      const result = await postAssessment(request);
      setState({
        status: "success",
        response: result.data,
        replayHeaders: result.replayHeaders,
        error: null,
      });
    } catch (err) {
      if (err instanceof AisApiError) {
        setState({
          status: "error",
          response: null,
          replayHeaders: null,
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
          replayHeaders: null,
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
