import type { AssistantRendering } from "../api/types";

interface RenderingPanelProps {
  rendering: AssistantRendering;
}

export function RenderingPanel({ rendering }: RenderingPanelProps) {
  return (
    <div className="space-y-4">
      {/* Warnings — non-dismissible alert banner, always visible when present */}
      {rendering.warnings.length > 0 && (
        <div className="rounded-md border border-red-300 bg-red-50 p-3">
          <p className="text-sm font-semibold text-red-800">Warnings</p>
          <ul className="mt-1 list-disc pl-5 text-sm text-red-700">
            {rendering.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Headline */}
      <h2 className="text-xl font-bold text-gray-900">{rendering.headline}</h2>

      {/* Summary */}
      <p className="text-base text-gray-700">{rendering.summary}</p>

      {/* Gap analysis — only when non-null */}
      {rendering.gap_analysis != null && (
        <div className="rounded-md border border-amber-300 bg-amber-50 p-3">
          <p className="text-sm font-semibold text-amber-800">Gap Analysis</p>
          <p className="mt-1 text-sm text-amber-700">{rendering.gap_analysis}</p>
        </div>
      )}

      {/* Fix strategy — only when non-null */}
      {rendering.fix_strategy != null && (
        <div className="rounded-md border border-blue-300 bg-blue-50 p-3">
          <p className="text-sm font-semibold text-blue-800">Fix Strategy</p>
          <p className="mt-1 text-sm text-blue-700">{rendering.fix_strategy}</p>
        </div>
      )}

      {/* Next steps — numbered list, always visible */}
      {rendering.next_steps.length > 0 && (
        <div>
          <p className="text-sm font-semibold text-gray-800">Next Steps</p>
          <ol className="mt-1 list-decimal pl-5 text-sm text-gray-700">
            {rendering.next_steps.map((step, i) => (
              <li key={i}>{step}</li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}
