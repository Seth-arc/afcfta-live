# Staged Data — Intermediate Pipeline Outputs

Working files between raw source documents and final processed outputs.

- extracted_text/ — full text from PDFs
- extracted_tables/ — tables from rule/tariff documents
- ocr/ — OCR outputs for scanned documents
- metadata/ — document metadata, structure maps
- normalized/ — standardized text before final processing

## Rules

- Every file traceable to a source in raw/ via source_id
- Staged files are regenerable — pipeline reruns overwrite them
- Do not manually edit — fix the parser instead
- Staged outputs do NOT go into the database. Only processed/ feeds the DB.
