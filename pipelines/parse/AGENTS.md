# Parser Rules

Convert raw source documents into structured extractions.

## By Document Type

- APPENDIX_RULE_TABLE: row-by-row PSR extraction (HS code, rule text, components, thresholds)
- TARIFF_SCHEDULE_TABLE: corridor + HS code + rates + year expansion
- LEGAL_TEXT: provision extraction (article_ref, verbatim text, topic, cross-refs)
- STATUS_NOTICE: entity + status_type + effective dates

## Rules

- Preserve verbatim text always
- Never infer status from absence of information
- HS codes may be chapter (2-digit) or heading (4-digit) — record actual hs_level
- Flag ambiguous entries rather than guessing
