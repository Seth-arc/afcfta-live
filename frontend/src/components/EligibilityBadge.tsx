import type { ConfidenceClass } from "../api/types";

interface EligibilityBadgeProps {
  eligible: boolean;
  confidenceClass: ConfidenceClass;
  ruleStatus: string;
}

type BadgeState = "eligible" | "not-eligible" | "incomplete";

function resolveBadgeState(
  eligible: boolean,
  confidenceClass: ConfidenceClass,
): BadgeState {
  if (confidenceClass === "incomplete") return "incomplete";
  if (eligible && confidenceClass === "complete") return "eligible";
  return "not-eligible";
}

const BADGE_STYLES: Record<BadgeState, { bg: string; text: string; border: string }> = {
  eligible: {
    bg: "bg-green-50",
    text: "text-green-800",
    border: "border-green-400",
  },
  "not-eligible": {
    bg: "bg-red-50",
    text: "text-red-800",
    border: "border-red-400",
  },
  incomplete: {
    bg: "bg-amber-50",
    text: "text-amber-800",
    border: "border-amber-400",
  },
};

const BADGE_LABELS: Record<BadgeState, string> = {
  eligible: "Eligible",
  "not-eligible": "Not Eligible",
  incomplete: "Incomplete",
};

export function EligibilityBadge({
  eligible,
  confidenceClass,
  ruleStatus,
}: EligibilityBadgeProps) {
  const state = resolveBadgeState(eligible, confidenceClass);
  const style = BADGE_STYLES[state];
  const showQualifier = ruleStatus === "pending" || ruleStatus === "provisional";

  return (
    <div
      className={`inline-flex items-center gap-2 rounded-lg border-2 px-4 py-2 ${style.bg} ${style.border}`}
    >
      <span className={`text-lg font-bold ${style.text}`}>
        {BADGE_LABELS[state]}
      </span>
      {showQualifier && (
        <span className="rounded-full bg-white/80 px-2 py-0.5 text-xs font-semibold text-gray-600 border border-gray-300">
          {ruleStatus}
        </span>
      )}
    </div>
  );
}
