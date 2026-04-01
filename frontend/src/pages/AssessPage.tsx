import { AssessmentForm } from "../components/AssessmentForm";
import { AssessmentResult } from "../components/AssessmentResult";
import { useAssessment } from "../hooks/useAssessment";

export function AssessPage() {
  const { status, response, replayHeaders, error, submit, reset } =
    useAssessment();

  return (
    <div className="mx-auto max-w-lg px-4 py-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">
        AfCFTA Eligibility Check
      </h1>

      <AssessmentForm onSubmit={submit} isLoading={status === "loading"} />

      {status === "error" && error && (
        <div className="mt-6 rounded-md border border-red-300 bg-red-50 p-4">
          <p className="text-sm font-semibold text-red-800">Request failed</p>
          <p className="mt-1 text-sm text-red-700">{error.message}</p>
          {error.retryAfterSeconds !== null && (
            <p className="mt-1 text-sm text-red-600">
              Retry after {error.retryAfterSeconds} seconds.
            </p>
          )}
          {error.requestId && (
            <p className="mt-2 text-xs text-gray-500">
              Request ID: <span className="font-mono">{error.requestId}</span>
            </p>
          )}
        </div>
      )}

      {status === "success" && response && (
        <div className="mt-6 space-y-4">
          <AssessmentResult
            assessment={response}
            replayHeaders={replayHeaders}
          />

          <button
            type="button"
            onClick={reset}
            className="w-full rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            Start new assessment
          </button>
        </div>
      )}
    </div>
  );
}
