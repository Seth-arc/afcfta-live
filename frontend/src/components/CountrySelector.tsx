import React from "react";

const SUPPORTED_COUNTRIES = [
  { code: "NGA", name: "Nigeria" },
  { code: "GHA", name: "Ghana" },
  { code: "CIV", name: "Cote d'Ivoire" },
  { code: "SEN", name: "Senegal" },
  { code: "CMR", name: "Cameroon" },
] as const;

interface CountrySelectorProps {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  disabledCode?: string;
  error?: string;
}

export function CountrySelector({
  id,
  label,
  value,
  onChange,
  disabledCode,
  error,
}: CountrySelectorProps) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-gray-700">
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={(e: React.ChangeEvent<HTMLSelectElement>) =>
          onChange(e.target.value)
        }
        className={`mt-1 block w-full rounded-md border px-3 py-2 shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${
          error ? "border-red-500" : "border-gray-300"
        }`}
      >
        <option value="">Select country</option>
        {SUPPORTED_COUNTRIES.map((c) => (
          <option key={c.code} value={c.code} disabled={c.code === disabledCode}>
            {c.name} ({c.code})
          </option>
        ))}
      </select>
      {error && <p className="mt-1 text-sm text-red-600">{error}</p>}
    </div>
  );
}
