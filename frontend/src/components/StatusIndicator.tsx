import type { ConfidenceClass } from "../api/types";

interface StatusIndicatorProps {
  ruleStatus: string;
  confidenceClass: ConfidenceClass;
}

export function StatusIndicator({
  ruleStatus,
  confidenceClass,
}: StatusIndicatorProps) {
  const isAgreed = ruleStatus === "agreed";
  const isProvisional = ruleStatus === "provisional";
  const isPending = ruleStatus === "pending";

  let pillClasses: string;
  let label: string;

  if (isAgreed) {
    pillClasses =
      "bg-gray-700 text-white border-gray-700";
    label = `${ruleStatus} · ${confidenceClass}`;
  } else if (isProvisional) {
    pillClasses =
      "bg-white text-amber-700 border-amber-500";
    label = `provisional · ${confidenceClass}`;
  } else if (isPending) {
    pillClasses =
      "bg-white text-orange-700 border-orange-500";
    label = `pending · ${confidenceClass}`;
  } else {
    pillClasses =
      "bg-gray-100 text-gray-700 border-gray-400";
    label = `${ruleStatus} · ${confidenceClass}`;
  }

  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${pillClasses}`}
    >
      {label}
    </span>
  );
}
