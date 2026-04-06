interface AuditLinkProps {
  caseId: string;
  evaluationId: string;
  auditUrl: string;
}

export function AuditLink({ caseId, evaluationId, auditUrl }: AuditLinkProps) {
  return (
    <div className="rounded-md border border-gray-200 bg-gray-50 px-4 py-3">
      <p className="text-sm font-semibold text-green-700">Decision recorded</p>
      <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs text-gray-600">
        <dt className="font-medium">Case</dt>
        <dd className="font-mono">{caseId}</dd>
        <dt className="font-medium">Evaluation</dt>
        <dd className="font-mono">{evaluationId}</dd>
      </dl>
      <a
        href={auditUrl}
        className="mt-2 inline-block text-xs font-medium text-blue-600 underline hover:text-blue-800"
      >
        View audit trail
      </a>
    </div>
  );
}
