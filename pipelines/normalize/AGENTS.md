# Normalization Rules

Convert extracted text into standardized machine-readable values.

## HS Codes: strip dots/spaces, digits only, record hs_version
## Rates: percentage strings → numeric, preserve precision, "Free" → 0.0000
## Countries: all references → ISO alpha-3 from app/core/countries.py
## Rule Components: "wholly obtained" → WO, "value added X%" → VA, etc.
## Status: map text patterns to status_type_enum. Never infer — flag ambiguity.

See the full reference in the combined AGENTS.md file for detailed mappings.
