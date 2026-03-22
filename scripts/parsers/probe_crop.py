import pdfplumber
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
PDF_PATH = (
    ROOT_DIR / "docs" / "corpus" / "02_rules_of_origin"
    / "EN-APPENDIX-IV-AS-AT-COM-12-DECEMBER-2023.pdf"
)

# Candidate crop boundaries
COL1 = (70, 180)    # HS code
COL2 = (180, 455)   # Description
COL3 = (455, 780)   # Rule text

# Test on one good page (17, idx 16) and one bad page (50, idx 49)
with pdfplumber.open(PDF_PATH) as pdf:
    for pg_idx in [16, 19, 49, 54]:
        page = pdf.pages[pg_idx]
        # Crop top/bottom to skip headers (y from ~60 to ~560)
        for col_name, (x0, x1) in [("COL1_HS", COL1), ("COL2_DESC", COL2), ("COL3_RULE", COL3)]:
            cropped = page.crop((x0, 60, x1, 560))
            text = cropped.extract_text() or ""
            # Show first 200 chars
            preview = text[:200].replace('\n', ' | ')
            print(f"Page {pg_idx+1} {col_name}: {preview}")
        print()