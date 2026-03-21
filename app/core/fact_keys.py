"""
Registry of valid fact_type values for case_input_fact.
The expression evaluator and fact_normalization_service use this
to validate inputs and compute derived variables.
"""

PRODUCTION_FACTS = {
    "ex_works": {"type": "number", "unit": "currency", "required_for": ["VNM", "VA"]},
    "non_originating": {"type": "number", "unit": "currency", "required_for": ["VNM", "VA"]},
    "fob_value": {"type": "number", "unit": "currency", "required_for": []},
    "customs_value": {"type": "number", "unit": "currency", "required_for": []},
    "originating_materials_value": {"type": "number", "unit": "currency", "required_for": []},
    "tariff_heading_input": {"type": "text", "required_for": ["CTH", "CTSH"]},
    "tariff_heading_output": {"type": "text", "required_for": ["CTH", "CTSH"]},
    "tariff_subheading_input": {"type": "text", "required_for": ["CTSH"]},
    "tariff_subheading_output": {"type": "text", "required_for": ["CTSH"]},
    "wholly_obtained": {"type": "boolean", "required_for": ["WO"]},
    "specific_process_performed": {"type": "boolean", "required_for": ["PROCESS"]},
    "specific_process_description": {"type": "text", "required_for": ["PROCESS"]},
    "direct_transport": {"type": "boolean", "required_for": ["general"]},
    "transshipment_country": {"type": "text", "required_for": []},
    "cumulation_claimed": {"type": "boolean", "required_for": ["general"]},
    "cumulation_partner_states": {"type": "list", "required_for": []},
}

DERIVED_VARIABLES = {
    "vnom_percent": "non_originating / ex_works * 100",
    "va_percent": "(ex_works - non_originating) / ex_works * 100",
}