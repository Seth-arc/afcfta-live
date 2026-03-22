import pdfplumber
from pathlib import Path
from collections import Counter

ROOT_DIR = Path(__file__).resolve().parents[2]
PDF_PATH = (
    ROOT_DIR / "docs" / "corpus" / "02_rules_of_origin"
    / "EN-APPENDIX-IV-AS-AT-COM-12-DECEMBER-2023.pdf"
)

with pdfplumber.open(PDF_PATH) as pdf:
    # Check page dimensions
    page = pdf.pages[16]  # Page 17 (0-indexed), known good page
    print(f"Page dimensions: {page.width} x {page.height}")
    print()

    # Get all characters with x-positions from pages 17-22 (good pages)
    all_x0 = []
    for pg_idx in [16, 17, 18, 19, 20]:
        page = pdf.pages[pg_idx]
        chars = page.chars
        for c in chars:
            all_x0.append(round(c["x0"], 0))

    # Find character position clusters to detect column boundaries
    x_counts = Counter(all_x0)
    print("Top 30 x-positions (column boundary candidates):")
    for x, count in sorted(x_counts.most_common(50), key=lambda t: t[0]):
        if count > 10:
            print(f"  x={x:6.0f}  count={count}")

    print()

    # Also check what tables pdfplumber finds on good vs bad pages
    for pg_idx in [16, 19, 48, 49, 54]:
        page = pdf.pages[pg_idx]
        tables = page.extract_tables()
        if tables:
            for ti, t in enumerate(tables):
                cols = max(len(row) for row in t if row)
                print(f"Page {pg_idx+1}: table {ti} has {cols} columns, {len(t)} rows")
        else:
            tables2 = page.extract_tables({"vertical_strategy": "text", "horizontal_strategy": "text"})
            if tables2:
                for ti, t in enumerate(tables2):
                    cols = max(len(row) for row in t if row)
                    print(f"Page {pg_idx+1} (text-mode): table {ti} has {cols} columns, {len(t)} rows")
            else:
                print(f"Page {pg_idx+1}: NO tables found")