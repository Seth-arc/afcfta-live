import { AssessmentForm } from "../components/AssessmentForm";
import { useAssessment } from "../hooks/useAssessment";
import type { EligibilityAssessmentResponse } from "../api/types";

function AssessmentPanel({
  assessment,
  auditUrl,
}: {
  assessment: EligibilityAssessmentResponse;
  auditUrl: string | null;
}) {
  const eligible = assessment.eligible;

  return (
    <div
      className={`rounded-md border p-4 ${
        eligible
          ? "border-green-300 bg-green-50"
          : "border-red-300 bg-red-50"
      }`}
    >
      <h3
        className={`text-lg font-bold ${
          eligible ? "text-green-800" : "text-red-800"
        }`}
      >
        {eligible ? "Eligible for preferential treatment" : "Not eligible"}
      </h3>

      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
        <dt className="font-medium text-gray-600">HS6 Code</dt>
        <dd>{assessment.hs6_code}</dd>

        <dt className="font-medium text-gray-600">Eligible</dt>
        <dd
          className={
            eligible
              ? "text-green-700 font-semibold"
              : "text-red-700 font-semibold"
          }
        >
          {eligible ? "Yes" : "No"}
        </dd>

        <dt className="font-medium text-gray-600">Pathway</dt>
        <dd>{assessment.pathway_used ?? "None"}</dd>

        <dt className="font-medium text-gray-600">Rule Status</dt>
        <dd>{assessment.rule_status}</dd>

        <dt className="font-medium text-gray-600">Confidence</dt>
        <dd>{assessment.confidence_class}</dd>

        {assessment.tariff_outcome && (
          <>
            <dt className="font-medium text-gray-600">Preferential Rate</dt>
            <dd>{assessment.tariff_outcome.preferential_rate ?? "N/A"}</dd>

            <dt className="font-medium text-gray-600">Base Rate</dt>
            <dd>{assessment.tariff_outcome.base_rate ?? "N/A"}</dd>
          </>
        )}
      </dl>

      {assessment.failures.length > 0 && (
        <div className="mt-3">
          <p className="text-sm font-medium text-red-700">Failures:</p>
          <ul className="mt-1 list-disc pl-5 text-sm text-red-600">
            {assessment.failures.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
        </div>
      )}

      {assessment.missing_facts.length > 0 && (
        <div className="mt-3">
          <p className="text-sm font-medium text-amber-700">Missing facts:</p>
          <ul className="mt-1 list-disc pl-5 text-sm text-amber-600">
            {assessment.missing_facts.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
        </div>
      )}

      {assessment.evidence_required.length > 0 && (
        <div className="mt-3">
          <p className="text-sm font-medium text-gray-600">
            Evidence required:
          </p>
          <ul className="mt-1 list-disc pl-5 text-sm text-gray-600">
            {assessment.evidence_required.map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
        </div>
      )}

      {auditUrl && (
        <p className="mt-3 text-xs text-gray-500">
          Audit trail: <span className="font-mono">{auditUrl}</span>
        </p>
      )}
    </div>
  );
}

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
          <AssessmentPanel
            assessment={response}
            auditUrl={replayHeaders?.auditUrl ?? null}
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
