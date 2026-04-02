import React from "react";

interface HsCodeInputProps {
  value: string;
  onChange: (value: string) => void;
  error?: string;
}

export function HsCodeInput({ value, onChange, error }: HsCodeInputProps) {
  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const digits = e.target.value.replace(/\D/g, "").slice(0, 6);
    onChange(digits);
  }

  return (
    <div>
      <label htmlFor="hs6_code" className="block text-sm font-medium text-gray-700">
        HS6 Product Code
      </label>
      <input
        id="hs6_code"
        type="text"
        inputMode="numeric"
        maxLength={6}
        placeholder="e.g. 110311"
        value={value}
        onChange={handleChange}
        className={`mt-1 block w-full rounded-md border px-3 py-2 shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${
          error ? "border-red-500" : "border-gray-300"
        }`}
      />
      {error && <p className="mt-1 text-sm text-red-600">{error}</p>}
    </div>
  );
}
