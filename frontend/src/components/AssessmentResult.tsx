import { useState } from "react";
import type { AssistantResponseEnvelope } from "../api/types";
import { EligibilityBadge } from "./EligibilityBadge";
import { StatusIndicator } from "./StatusIndicator";
import { RenderingPanel } from "./RenderingPanel";
import { TariffCard } from "./TariffCard";
import { AuditLink } from "./AuditLink";

interface AssessmentResultProps {
  envelope: AssistantResponseEnvelope;
}

export function AssessmentResult({ envelope }: AssessmentResultProps) {
  const [explanationOpen, setExplanationOpen] = useState(false);
  const { assessment, assistant_rendering, explanation } = envelope;

  if (envelope.response_type === "error" && envelope.error) {
    return (
      <div className="rounded-md border border-red-300 bg-red-50 p-4">
        <p className="text-sm font-semibold text-red-800">Assistant request rejected</p>
        <p className="mt-1 text-sm text-red-700">{envelope.error.message}</p>
        <p className="mt-2 text-xs text-red-600">Code: {envelope.error.code}</p>
      </div>
    );
  }

  if (envelope.response_type === "clarification" && envelope.clarification) {
    return (
      <div className="space-y-4 rounded-md border border-amber-300 bg-amber-50 p-4">
        <div>
          <p className="text-sm font-semibold text-amber-800">
            More information required
          </p>
          <p className="mt-1 text-sm text-amber-700">
            {envelope.clarification.question}
          </p>
        </div>

        {envelope.clarification.missing_facts.length > 0 && (
          <div>
            <p className="text-sm font-medium text-amber-800">Missing facts</p>
            <ul className="mt-1 list-disc pl-5 text-sm text-amber-700">
              {envelope.clarification.missing_facts.map((fact) => (
                <li key={fact}>{fact}</li>
              ))}
            </ul>
          </div>
        )}

        {envelope.clarification.missing_evidence.length > 0 && (
          <div>
            <p className="text-sm font-medium text-amber-800">Missing evidence</p>
            <ul className="mt-1 list-disc pl-5 text-sm text-amber-700">
              {envelope.clarification.missing_evidence.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    );
  }

  if (!assessment) return null;

  return (
    <div className="space-y-5">
      {/* Eligibility badge + status indicator — always together */}
      <div className="flex items-center gap-3 flex-wrap">
        <EligibilityBadge
          eligible={assessment.eligible}
          confidenceClass={assessment.confidence_class}
          ruleStatus={assessment.rule_status}
        />
        <StatusIndicator
          ruleStatus={assessment.rule_status}
          confidenceClass={assessment.confidence_class}
        />
      </div>

      {/* Rendering panel — works with both NIM-rendered and deterministic-fallback */}
      {assistant_rendering && (
        <RenderingPanel rendering={assistant_rendering} />
      )}

      {/* Tariff card */}
      {assessment.tariff_outcome && (
        <TariffCard
          tariffOutcome={assessment.tariff_outcome}
          eligible={assessment.eligible}
          ruleStatus={assessment.rule_status}
          confidenceClass={assessment.confidence_class}
        />
      )}

      {/* Failures */}
      {assessment.failures.length > 0 && (
        <div>
          <p className="text-sm font-medium text-red-700">Failures:</p>
          <ul className="mt-1 list-disc pl-5 text-sm text-red-600">
            {assessment.failures.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Missing facts */}
      {assessment.missing_facts.length > 0 && (
        <div>
          <p className="text-sm font-medium text-amber-700">Missing facts:</p>
          <ul className="mt-1 list-disc pl-5 text-sm text-amber-600">
            {assessment.missing_facts.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Evidence required */}
      {assessment.evidence_required.length > 0 && (
        <div>
          <p className="text-sm font-medium text-gray-600">Evidence required:</p>
          <ul className="mt-1 list-disc pl-5 text-sm text-gray-600">
            {assessment.evidence_required.map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Explanation — collapsible section */}
      {explanation != null && (
        <div className="border-t border-gray-200 pt-3">
          <button
            type="button"
            onClick={() => setExplanationOpen(!explanationOpen)}
            className="flex items-center gap-1 text-sm font-medium text-gray-700 hover:text-gray-900"
          >
            <span className="text-xs">{explanationOpen ? "▼" : "▶"}</span>
            Explanation
            {envelope.explanation_fallback_used && (
              <span className="ml-1 text-xs text-gray-400">(fallback)</span>
            )}
          </button>
          {explanationOpen && (
            <p className="mt-2 text-sm text-gray-600">{explanation}</p>
          )}
        </div>
      )}

      {/* Audit link — only when audit_persisted is true */}
      {envelope.audit_persisted &&
        envelope.case_id &&
        envelope.evaluation_id &&
        envelope.audit_url && (
          <AuditLink
            caseId={envelope.case_id}
            evaluationId={envelope.evaluation_id}
            auditUrl={envelope.audit_url}
          />
        )}
    </div>
  );
}
