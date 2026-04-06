import type { TariffOutcome } from "../api/types";
import { StatusIndicator } from "./StatusIndicator";
import type { ConfidenceClass } from "../api/types";

interface TariffCardProps {
  tariffOutcome: TariffOutcome;
  eligible: boolean;
  ruleStatus: string;
  confidenceClass: ConfidenceClass;
}

export function TariffCard({
  tariffOutcome,
  eligible,
  ruleStatus,
  confidenceClass,
}: TariffCardProps) {
  return (
    <div className="rounded-md border border-gray-200 bg-white p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-800">Tariff Outcome</h3>
        <StatusIndicator ruleStatus={ruleStatus} confidenceClass={confidenceClass} />
      </div>

      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
        {/* Preferential rate — emphasized when eligible */}
        <dt className="font-medium text-gray-600">Preferential Rate</dt>
        <dd
          className={
            eligible
              ? "font-bold text-green-700"
              : "text-gray-700"
          }
        >
          {tariffOutcome.preferential_rate ?? "N/A"}
        </dd>

        {/* Base rate — emphasized when not eligible */}
        <dt className="font-medium text-gray-600">Base Rate</dt>
        <dd
          className={
            !eligible
              ? "font-bold text-red-700"
              : "text-gray-700"
          }
        >
          {tariffOutcome.base_rate ?? "N/A"}
          {!eligible && (
            <span className="ml-1 text-xs text-red-500">without preference</span>
          )}
        </dd>

        <dt className="font-medium text-gray-600">Tariff Status</dt>
        <dd className="text-gray-700">{tariffOutcome.status}</dd>
      </dl>
    </div>
  );
}
