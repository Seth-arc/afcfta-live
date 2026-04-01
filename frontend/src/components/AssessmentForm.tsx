import React, { useState } from "react";
import { HsCodeInput } from "./HsCodeInput";
import { CountrySelector } from "./CountrySelector";
import type { AssessmentRequest } from "../api/types";

interface AssessmentFormProps {
  onSubmit: (request: AssessmentRequest) => void;
  isLoading: boolean;
}

interface FormErrors {
  hs6Code?: string;
  exporter?: string;
  importer?: string;
  year?: string;
}

const CURRENT_YEAR = new Date().getFullYear();

export function AssessmentForm({ onSubmit, isLoading }: AssessmentFormProps) {
  const [hs6Code, setHs6Code] = useState("");
  const [exporter, setExporter] = useState("");
  const [importer, setImporter] = useState("");
  const [year, setYear] = useState(CURRENT_YEAR);
  const [errors, setErrors] = useState<FormErrors>({});

  function validate(): FormErrors {
    const next: FormErrors = {};
    if (!/^\d{6}$/.test(hs6Code)) {
      next.hs6Code = "HS6 code must be exactly 6 digits.";
    }
    if (!exporter) {
      next.exporter = "Select an exporter country.";
    }
    if (!importer) {
      next.importer = "Select an importer country.";
    }
    if (exporter && importer && exporter === importer) {
      next.importer = "Importer must be different from exporter.";
    }
    if (year < 2020 || year > 2040) {
      next.year = "Year must be between 2020 and 2040.";
    }
    return next;
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const formErrors = validate();
    setErrors(formErrors);
    if (Object.keys(formErrors).length > 0) return;

    const outputHeading = hs6Code.slice(0, 4);

    const request: AssessmentRequest = {
      hs6_code: hs6Code,
      hs_version: "HS2017",
      exporter,
      importer,
      year,
      persona_mode: "exporter",
      production_facts: [
        {
          fact_type: "tariff_heading_output",
          fact_key: "tariff_heading_output",
          fact_value_type: "text",
          fact_value_text: outputHeading,
        },
        {
          fact_type: "direct_transport",
          fact_key: "direct_transport",
          fact_value_type: "boolean",
          fact_value_boolean: true,
        },
      ],
    };
    onSubmit(request);
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <HsCodeInput value={hs6Code} onChange={setHs6Code} error={errors.hs6Code} />

      <CountrySelector
        id="exporter"
        label="Exporter Country"
        value={exporter}
        onChange={setExporter}
        disabledCode={importer}
        error={errors.exporter}
      />

      <CountrySelector
        id="importer"
        label="Importer Country"
        value={importer}
        onChange={setImporter}
        disabledCode={exporter}
        error={errors.importer}
      />

      <div>
        <label htmlFor="year" className="block text-sm font-medium text-gray-700">
          Year
        </label>
        <input
          id="year"
          type="number"
          min={2020}
          max={2040}
          value={year}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
            setYear(Number(e.target.value))
          }
          className={`mt-1 block w-full rounded-md border px-3 py-2 shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${
            errors.year ? "border-red-500" : "border-gray-300"
          }`}
        />
        {errors.year && <p className="mt-1 text-sm text-red-600">{errors.year}</p>}
      </div>

      <button
        type="submit"
        disabled={isLoading}
        className="w-full rounded-md bg-blue-600 px-4 py-2 text-white font-medium hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {isLoading ? "Checking eligibility..." : "Check Eligibility"}
      </button>
    </form>
  );
}
