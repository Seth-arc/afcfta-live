import re

def deduplicate_text(text):
    """Collapse every pair of identical adjacent characters to one."""
    if not text:
        return text
    return re.sub(r'(.)\1', r'\1', text)

# Test cases from your CSV
samples = [
    "AAFFRRIICCAANN CCOONNTTIINNEENNTTAALL",
    "TThhee sseeccoonndd ccoolluummnn ggiivv",
    "PPRROOCCEESSSSIINNGG CCAARRRRII",
    "CCoolluummnn 33",
]

for s in samples:
    print(f"{s}")
    print(f"  → {deduplicate_text(s)}")
    print()