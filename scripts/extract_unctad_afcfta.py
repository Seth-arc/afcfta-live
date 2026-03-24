#!/usr/bin/env python3
"""
extract_unctad_afcfta.py
========================
UNCTAD AfCFTA Tariff Schedule Extraction & AIS Schema Transformation

Fetches tariff elimination data from the UNCTAD AfCFTA e-Tariff API
for all v0.1 corridor permutations and transforms it into CSV files
aligned with the AIS database schema (L3 — Tariff Layer).

Target tables:
  - tariff_schedule_header
  - tariff_schedule_line
  - tariff_schedule_rate_by_year

API endpoint pattern:
  https://afcfta-api.unctad.org/tariffseliminationnew!{reporter}&{partner}&{product}

Where:
  reporter = UNCTAD country ID of the importing state
  partner  = UNCTAD country ID of the exporting state
  product  = 0 (all products)

Usage:
  python extract_unctad_afcfta.py
  python extract_unctad_afcfta.py --output-dir ./tariff_data
  python extract_unctad_afcfta.py --base-year 2021 --dry-run
  python extract_unctad_afcfta.py --corridors GHA-NGA,CMR-GHA

Requirements:
  pip install requests
"""

import argparse
import csv
import hashlib
import json
import logging
import sys
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from itertools import permutations
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: 'requests' library is required. Install with: pip install requests")
    sys.exit(1)


# =============================================================================
# CONFIGURATION
# =============================================================================

# v0.1 country registry: ISO3 → UNCTAD country ID
COUNTRY_REGISTRY = {
    "CMR": {"unctad_id": "15", "name": "Cameroon"},
    "CIV": {"unctad_id": "20", "name": "Côte d'Ivoire"},
    "GHA": {"unctad_id": "29", "name": "Ghana"},
    "NGA": {"unctad_id": "44", "name": "Nigeria"},
    "SEN": {"unctad_id": "47", "name": "Senegal"},
}

# API configuration
API_BASE_URL = "https://afcfta-api.unctad.org"
API_ENDPOINT_TEMPLATE = "/tariffseliminationnew!{reporter}&{partner}&{product}"
REQUEST_TIMEOUT = 60  # seconds
RETRY_ATTEMPTS = 3
RETRY_DELAY = 5  # seconds between retries
REQUEST_DELAY = 2  # seconds between corridor requests (rate limiting)

# AfCFTA implementation start year — t1 corresponds to this year
DEFAULT_BASE_YEAR = 2021

# AIS schema enum mappings
# UNCTAD category → tariff_category_enum
TARIFF_CATEGORY_MAP = {
    "A": "liberalised",   # Non-sensitive: 5yr (non-LDC) / 10yr (LDC) phase-down
    "B": "sensitive",     # Sensitive: 10yr (non-LDC) / 13yr (LDC) phase-down
    "C": "excluded",      # Excluded from liberalisation
    "D": "sensitive",     # Some schedules use D for sensitive sub-categories
    "E": "excluded",      # Some schedules use E for exclusions
}

# Source metadata for provenance tracking
SOURCE_METADATA = {
    "title": "UNCTAD AfCFTA e-Tariff Database — Tariff Elimination Schedules",
    "short_title": "UNCTAD-AFCFTA-ETARIFF",
    "source_group": "03_tariff_schedules",
    "source_type": "tariff_schedule",
    "authority_tier": "official_operational",
    "issuing_body": "United Nations Conference on Trade and Development (UNCTAD)",
    "jurisdiction_scope": "afcfta",
    "language": "en",
    "hs_version": "HS2017",
    "source_url": "https://afcfta.unctad.org",
}


# =============================================================================
# LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("unctad_extractor")


# =============================================================================
# HELPERS
# =============================================================================

def generate_uuid():
    """Generate a new UUID v4 string."""
    return str(uuid.uuid4())


def now_iso():
    """Return current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def safe_decimal(value):
    """
    Parse a value to Decimal safely.
    Returns None if the value is None, empty, or unparseable.
    """
    if value is None:
        return None
    value_str = str(value).strip()
    if value_str == "" or value_str.lower() == "null":
        return None
    try:
        return Decimal(value_str)
    except (InvalidOperation, ValueError):
        logger.warning("Could not parse decimal value: %r", value)
        return None


def safe_int(value):
    """Parse a value to int safely. Returns None on failure."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def compute_checksum(data_bytes):
    """Compute SHA-256 hex digest of raw bytes."""
    return hashlib.sha256(data_bytes).hexdigest()


def classify_staging_type(mfn_rate, no_years, year_rates):
    """
    Determine the staging_type_enum value based on the phase-down pattern.

    Returns one of: 'immediate', 'linear', 'stepwise', 'unknown'
    """
    if mfn_rate is None or no_years is None:
        return "unknown"

    # If MFN is 0 or already at target, it's immediate
    if mfn_rate == Decimal("0") or no_years == 0:
        return "immediate"

    # Check if we have year rates to analyze
    non_null_rates = [r for r in year_rates if r is not None]
    if len(non_null_rates) < 2:
        return "unknown"

    # Check for linear pattern: equal steps between each year
    steps = []
    for i in range(1, len(non_null_rates)):
        step = non_null_rates[i - 1] - non_null_rates[i]
        steps.append(step)

    if not steps:
        return "unknown"

    # All steps equal (within rounding tolerance) → linear
    first_step = steps[0]
    tolerance = Decimal("0.01")
    if all(abs(s - first_step) <= tolerance for s in steps):
        return "linear"

    return "stepwise"


def map_tariff_category(category_code):
    """Map UNCTAD category letter to tariff_category_enum value."""
    if category_code is None:
        return "unknown"
    return TARIFF_CATEGORY_MAP.get(str(category_code).strip().upper(), "unknown")


def derive_target_rate(year_rates, no_years):
    """
    Derive the target (final) rate from the year rate columns.
    The last non-null t{n} value is the target rate.
    """
    for i in range(no_years, 0, -1) if no_years else range(13, 0, -1):
        rate = year_rates.get(i)
        if rate is not None:
            return rate
    return None


# =============================================================================
# API CLIENT
# =============================================================================

class UNCTADClient:
    """HTTP client for the UNCTAD AfCFTA tariff API."""

    def __init__(self, base_url=API_BASE_URL, timeout=REQUEST_TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "AIS-AfCFTA-Extractor/1.0",
        })

    def fetch_corridor(self, reporter_id, partner_id, product="0"):
        """
        Fetch tariff elimination data for a single corridor.

        Args:
            reporter_id: UNCTAD country ID of the importing state
            partner_id:  UNCTAD country ID of the exporting state
            product:     Product filter ("0" = all products)

        Returns:
            list[dict] on success, or None if no data / error
        """
        endpoint = API_ENDPOINT_TEMPLATE.format(
            reporter=reporter_id,
            partner=partner_id,
            product=product,
        )
        url = f"{self.base_url}{endpoint}"

        for attempt in range(1, RETRY_ATTEMPTS + 1):
            try:
                logger.info(
                    "Fetching %s (attempt %d/%d)",
                    url, attempt, RETRY_ATTEMPTS,
                )
                resp = self.session.get(url, timeout=self.timeout)

                # Check for non-200 status
                if resp.status_code != 200:
                    logger.warning(
                        "HTTP %d for %s", resp.status_code, url,
                    )
                    if attempt < RETRY_ATTEMPTS:
                        time.sleep(RETRY_DELAY)
                        continue
                    return None

                # Check content type — HTML response means no data available
                content_type = resp.headers.get("Content-Type", "")
                if "text/html" in content_type:
                    logger.warning(
                        "Received HTML response (SPA fallback) for %s — "
                        "no tariff data available for this corridor",
                        url,
                    )
                    return None

                # Attempt JSON parse
                try:
                    data = resp.json()
                except (json.JSONDecodeError, ValueError):
                    # Check if the response body looks like HTML
                    body_start = resp.text[:200].strip().lower()
                    if body_start.startswith("<!doctype") or body_start.startswith("<html"):
                        logger.warning(
                            "Response body is HTML despite JSON content-type "
                            "for %s — no data available",
                            url,
                        )
                        return None
                    logger.error(
                        "JSON parse error for %s: %s",
                        url, resp.text[:200],
                    )
                    if attempt < RETRY_ATTEMPTS:
                        time.sleep(RETRY_DELAY)
                        continue
                    return None

                # Validate response structure
                if isinstance(data, list):
                    if len(data) == 0:
                        logger.info("Empty array returned for %s", url)
                        return []
                    return data
                else:
                    logger.warning(
                        "Unexpected response type %s for %s",
                        type(data).__name__, url,
                    )
                    return None

            except requests.exceptions.Timeout:
                logger.warning("Timeout for %s (attempt %d)", url, attempt)
                if attempt < RETRY_ATTEMPTS:
                    time.sleep(RETRY_DELAY)
            except requests.exceptions.ConnectionError as e:
                logger.warning("Connection error for %s: %s", url, e)
                if attempt < RETRY_ATTEMPTS:
                    time.sleep(RETRY_DELAY)
            except requests.exceptions.RequestException as e:
                logger.error("Request error for %s: %s", url, e)
                if attempt < RETRY_ATTEMPTS:
                    time.sleep(RETRY_DELAY)

        logger.error("All %d attempts failed for %s", RETRY_ATTEMPTS, url)
        return None

    def close(self):
        """Close the HTTP session."""
        self.session.close()


# =============================================================================
# TRANSFORMER
# =============================================================================

class AISTransformer:
    """
    Transforms raw UNCTAD API responses into AIS-schema-aligned records
    for the three tariff tables:
      - tariff_schedule_header
      - tariff_schedule_line
      - tariff_schedule_rate_by_year
    """

    def __init__(self, base_year=DEFAULT_BASE_YEAR):
        self.base_year = base_year
        self.headers = []      # tariff_schedule_header rows
        self.lines = []        # tariff_schedule_line rows
        self.year_rates = []   # tariff_schedule_rate_by_year rows
        self.roo_crossref = [] # bonus: roO_Category cross-reference records
        self._source_id = generate_uuid()  # single source_id for this extraction run

        # Track generated header IDs to avoid duplicates
        self._header_cache = {}  # (importer, exporter, scheme) → schedule_id

    @property
    def source_id(self):
        return self._source_id

    def get_or_create_header(self, importer_iso3, exporter_iso3, scheme):
        """
        Get or create a tariff_schedule_header for a corridor + scheme.
        Returns the schedule_id.
        """
        cache_key = (importer_iso3, exporter_iso3, scheme)
        if cache_key in self._header_cache:
            return self._header_cache[cache_key]

        schedule_id = generate_uuid()
        header = {
            "schedule_id": schedule_id,
            "source_id": self._source_id,
            "importing_state": importer_iso3,
            "exporting_scope": exporter_iso3,
            "schedule_status": "official",
            "publication_date": None,
            "effective_date": f"{self.base_year}-01-01",
            "expiry_date": None,
            "hs_version": SOURCE_METADATA["hs_version"],
            "category_system": f"scheme_{scheme}" if scheme else None,
            "notes": (
                f"Extracted from UNCTAD AfCFTA e-Tariff API on {now_iso()}. "
                f"Corridor: {exporter_iso3} → {importer_iso3}."
            ),
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        self.headers.append(header)
        self._header_cache[cache_key] = schedule_id
        return schedule_id

    def transform_corridor(self, importer_iso3, exporter_iso3, raw_records):
        """
        Transform a list of raw UNCTAD API records for one corridor
        into AIS-schema rows.

        Args:
            importer_iso3: ISO3 code of importing state (the reporter)
            exporter_iso3: ISO3 code of exporting state (the partner)
            raw_records:   list of dicts from the API response
        """
        if not raw_records:
            return

        line_count = 0
        rate_count = 0

        for record in raw_records:
            # --- Extract raw fields ---
            nat_tar_line = str(record.get("natTarLine", "")).strip()
            description = str(record.get("descr", "")).strip()
            category = record.get("category")
            mfn_raw = record.get("mfn")
            no_years_raw = record.get("no_Years")
            scheme = record.get("scheme")
            hs_type = record.get("hS_Type")
            roo_category = record.get("roO_Category")

            # Skip records with no tariff line code
            if not nat_tar_line:
                logger.warning("Skipping record with empty natTarLine: %r", record)
                continue

            # --- Parse numeric fields ---
            mfn_rate = safe_decimal(mfn_raw)
            no_years = safe_int(no_years_raw)

            # --- Collect year rates (t1 through t13) ---
            year_rate_map = {}  # year_offset → Decimal rate
            year_rate_list = []  # for staging type classification
            for n in range(1, 14):
                field_name = f"t{n}"
                raw_val = record.get(field_name)
                parsed = safe_decimal(raw_val)
                year_rate_map[n] = parsed
                year_rate_list.append(parsed)

            # --- Derive computed fields ---
            tariff_cat = map_tariff_category(category)
            staging = classify_staging_type(mfn_rate, no_years, year_rate_list)
            target_rate = derive_target_rate(year_rate_map, no_years)
            target_year = (self.base_year + no_years) if no_years else None

            # --- Get or create header ---
            schedule_id = self.get_or_create_header(
                importer_iso3, exporter_iso3, scheme,
            )

            # --- Create tariff_schedule_line ---
            line_id = generate_uuid()
            line = {
                "schedule_line_id": line_id,
                "schedule_id": schedule_id,
                "hs_code": nat_tar_line,
                "product_description": description,
                "tariff_category": tariff_cat,
                "mfn_base_rate": str(mfn_rate) if mfn_rate is not None else None,
                "base_year": self.base_year,
                "target_rate": str(target_rate) if target_rate is not None else None,
                "target_year": target_year,
                "staging_type": staging,
                "page_ref": None,
                "table_ref": f"hs_type_{hs_type}" if hs_type else None,
                "row_ref": nat_tar_line,  # unique row identifier within schedule
                "created_at": now_iso(),
                "updated_at": now_iso(),
            }
            self.lines.append(line)
            line_count += 1

            # --- Create tariff_schedule_rate_by_year rows ---
            for year_offset, rate in year_rate_map.items():
                if rate is not None:
                    calendar_year = self.base_year + year_offset
                    year_rate_row = {
                        "year_rate_id": generate_uuid(),
                        "schedule_line_id": line_id,
                        "calendar_year": calendar_year,
                        "preferential_rate": str(rate),
                        "rate_status": "projected",
                        "source_id": self._source_id,
                        "page_ref": None,
                        "created_at": now_iso(),
                        "updated_at": now_iso(),
                    }
                    self.year_rates.append(year_rate_row)
                    rate_count += 1

            # --- Bonus: capture RoO cross-reference ---
            if roo_category:
                self.roo_crossref.append({
                    "hs_code": nat_tar_line,
                    "hs6": nat_tar_line[:6],
                    "roo_category": roo_category,
                    "importer": importer_iso3,
                    "exporter": exporter_iso3,
                    "scheme": scheme,
                })

        logger.info(
            "Transformed %s → %s: %d lines, %d year-rate rows",
            exporter_iso3, importer_iso3, line_count, rate_count,
        )

    def get_source_registry_row(self, checksum=""):
        """
        Generate a source_registry record for this extraction run.
        """
        return {
            "source_id": self._source_id,
            "title": SOURCE_METADATA["title"],
            "short_title": SOURCE_METADATA["short_title"],
            "source_group": SOURCE_METADATA["source_group"],
            "source_type": SOURCE_METADATA["source_type"],
            "authority_tier": SOURCE_METADATA["authority_tier"],
            "issuing_body": SOURCE_METADATA["issuing_body"],
            "jurisdiction_scope": SOURCE_METADATA["jurisdiction_scope"],
            "country_code": None,
            "customs_union_code": None,
            "publication_date": None,
            "effective_date": f"{self.base_year}-01-01",
            "expiry_date": None,
            "version_label": f"extraction_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            "status": "current",
            "language": SOURCE_METADATA["language"],
            "hs_version": SOURCE_METADATA["hs_version"],
            "file_path": "unctad_afcfta_api",
            "mime_type": "application/json",
            "source_url": SOURCE_METADATA["source_url"],
            "checksum_sha256": checksum,
            "citation_preferred": (
                "UNCTAD AfCFTA e-Tariff Database, "
                "Tariff Elimination Schedules. "
                f"Retrieved {datetime.now(timezone.utc).strftime('%Y-%m-%d')}. "
                "https://afcfta.unctad.org"
            ),
            "notes": (
                f"Automated extraction via extract_unctad_afcfta.py. "
                f"Base year: {self.base_year}."
            ),
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }


# =============================================================================
# CSV WRITER
# =============================================================================

class CSVWriter:
    """Writes AIS-schema-aligned CSV files for database ingestion."""

    HEADER_COLUMNS = [
        "schedule_id", "source_id", "importing_state", "exporting_scope",
        "schedule_status", "publication_date", "effective_date", "expiry_date",
        "hs_version", "category_system", "notes", "created_at", "updated_at",
    ]

    LINE_COLUMNS = [
        "schedule_line_id", "schedule_id", "hs_code", "product_description",
        "tariff_category", "mfn_base_rate", "base_year", "target_rate",
        "target_year", "staging_type", "page_ref", "table_ref", "row_ref",
        "created_at", "updated_at",
    ]

    YEAR_RATE_COLUMNS = [
        "year_rate_id", "schedule_line_id", "calendar_year",
        "preferential_rate", "rate_status", "source_id", "page_ref",
        "created_at", "updated_at",
    ]

    SOURCE_COLUMNS = [
        "source_id", "title", "short_title", "source_group", "source_type",
        "authority_tier", "issuing_body", "jurisdiction_scope", "country_code",
        "customs_union_code", "publication_date", "effective_date", "expiry_date",
        "version_label", "status", "language", "hs_version", "file_path",
        "mime_type", "source_url", "checksum_sha256", "citation_preferred",
        "notes", "created_at", "updated_at",
    ]

    ROO_CROSSREF_COLUMNS = [
        "hs_code", "hs6", "roo_category", "importer", "exporter", "scheme",
    ]

    @staticmethod
    def write_csv(filepath, columns, rows):
        """Write a list of dicts to CSV with the given column order."""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

        logger.info("Wrote %d rows to %s", len(rows), filepath)

    @classmethod
    def write_all(cls, output_dir, transformer):
        """
        Write all transformed data to CSV files in the output directory.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Compute a checksum over all raw data for provenance
        all_data_str = json.dumps({
            "headers": len(transformer.headers),
            "lines": len(transformer.lines),
            "year_rates": len(transformer.year_rates),
        }, sort_keys=True)
        checksum = compute_checksum(all_data_str.encode("utf-8"))

        # Source registry
        source_row = transformer.get_source_registry_row(checksum)
        cls.write_csv(
            output_dir / "source_registry.csv",
            cls.SOURCE_COLUMNS,
            [source_row],
        )

        # Tariff schedule headers
        cls.write_csv(
            output_dir / "tariff_schedule_header.csv",
            cls.HEADER_COLUMNS,
            transformer.headers,
        )

        # Tariff schedule lines
        cls.write_csv(
            output_dir / "tariff_schedule_line.csv",
            cls.LINE_COLUMNS,
            transformer.lines,
        )

        # Year rates
        cls.write_csv(
            output_dir / "tariff_schedule_rate_by_year.csv",
            cls.YEAR_RATE_COLUMNS,
            transformer.year_rates,
        )

        # RoO cross-reference (bonus — not a core table but useful)
        if transformer.roo_crossref:
            cls.write_csv(
                output_dir / "roo_crossref.csv",
                cls.ROO_CROSSREF_COLUMNS,
                transformer.roo_crossref,
            )

        # Raw JSON backup of all corridors (for provenance)
        raw_backup = {
            "extraction_timestamp": now_iso(),
            "base_year": transformer.base_year,
            "source_id": transformer.source_id,
            "counts": {
                "headers": len(transformer.headers),
                "lines": len(transformer.lines),
                "year_rates": len(transformer.year_rates),
                "roo_crossref": len(transformer.roo_crossref),
            },
        }
        backup_path = output_dir / "extraction_metadata.json"
        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump(raw_backup, f, indent=2, default=str)
        logger.info("Wrote extraction metadata to %s", backup_path)

        # Summary report
        summary_path = output_dir / "extraction_summary.txt"
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write("UNCTAD AfCFTA Tariff Extraction Summary\n")
            f.write("=" * 50 + "\n")
            f.write(f"Extraction time: {now_iso()}\n")
            f.write(f"Base year:       {transformer.base_year}\n")
            f.write(f"Source ID:       {transformer.source_id}\n")
            f.write(f"Checksum:        {checksum}\n\n")
            f.write(f"Schedule headers:       {len(transformer.headers):>8,}\n")
            f.write(f"Schedule lines:         {len(transformer.lines):>8,}\n")
            f.write(f"Year rate rows:         {len(transformer.year_rates):>8,}\n")
            f.write(f"RoO cross-references:   {len(transformer.roo_crossref):>8,}\n\n")

            f.write("Corridors by header:\n")
            for h in transformer.headers:
                exporter = h["exporting_scope"]
                importer = h["importing_state"]
                scheme = h["category_system"] or "default"
                line_count = sum(
                    1 for line in transformer.lines
                    if line["schedule_id"] == h["schedule_id"]
                )
                f.write(f"  {exporter} → {importer} ({scheme}): {line_count:,} lines\n")

        logger.info("Wrote summary to %s", summary_path)


# =============================================================================
# RAW JSON SAVER (for provenance — keeps the untransformed API responses)
# =============================================================================

def save_raw_response(output_dir, importer_iso3, exporter_iso3, raw_records):
    """Save the raw API response JSON for a corridor."""
    raw_dir = Path(output_dir) / "raw_api_responses"
    raw_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{exporter_iso3}_to_{importer_iso3}.json"
    filepath = raw_dir / filename
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(raw_records, f, indent=2, default=str)
    logger.info("Saved raw response: %s (%d records)", filepath, len(raw_records))


# =============================================================================
# CORRIDOR MATRIX
# =============================================================================

def build_corridor_matrix(corridors_filter=None):
    """
    Build the list of (importer, exporter) corridor pairs to fetch.

    Args:
        corridors_filter: Optional comma-separated string like "GHA-NGA,CMR-GHA"
                          where each pair is EXPORTER-IMPORTER.
                          If None, generates all 20 permutations.

    Returns:
        list of (importer_iso3, exporter_iso3) tuples
    """
    if corridors_filter:
        pairs = []
        for pair_str in corridors_filter.split(","):
            parts = pair_str.strip().upper().split("-")
            if len(parts) != 2:
                logger.warning("Invalid corridor format: %r (expected EXP-IMP)", pair_str)
                continue
            exporter, importer = parts[0], parts[1]
            if exporter not in COUNTRY_REGISTRY:
                logger.warning("Unknown exporter: %s", exporter)
                continue
            if importer not in COUNTRY_REGISTRY:
                logger.warning("Unknown importer: %s", importer)
                continue
            pairs.append((importer, exporter))
        return pairs

    # All 20 permutations of 5 countries
    countries = list(COUNTRY_REGISTRY.keys())
    return list(permutations(countries, 2))


# =============================================================================
# MAIN EXTRACTION PIPELINE
# =============================================================================

def run_extraction(output_dir, base_year, corridors_filter=None, dry_run=False):
    """
    Execute the full extraction pipeline:
    1. Build corridor matrix
    2. Fetch data from UNCTAD API for each corridor
    3. Transform to AIS schema
    4. Write CSV files

    Args:
        output_dir:       Path to output directory
        base_year:        AfCFTA implementation start year (t1 = this year)
        corridors_filter: Optional corridor filter string
        dry_run:          If True, skip API calls and show what would be fetched
    """
    corridor_matrix = build_corridor_matrix(corridors_filter)
    logger.info(
        "Corridor matrix: %d pairs to fetch",
        len(corridor_matrix),
    )

    if dry_run:
        logger.info("DRY RUN — listing corridors without fetching:")
        for importer, exporter in corridor_matrix:
            imp_id = COUNTRY_REGISTRY[importer]["unctad_id"]
            exp_id = COUNTRY_REGISTRY[exporter]["unctad_id"]
            logger.info(
                "  %s (%s) → %s (%s): tariffseliminationnew!%s&%s&0",
                exporter,
                COUNTRY_REGISTRY[exporter]["name"],
                importer,
                COUNTRY_REGISTRY[importer]["name"],
                imp_id, exp_id,
            )
        return

    client = UNCTADClient()
    transformer = AISTransformer(base_year=base_year)

    successful = 0
    no_data = 0
    total_records = 0

    try:
        for i, (importer, exporter) in enumerate(corridor_matrix):
            imp_id = COUNTRY_REGISTRY[importer]["unctad_id"]
            exp_id = COUNTRY_REGISTRY[exporter]["unctad_id"]

            logger.info(
                "[%d/%d] Fetching %s → %s (reporter=%s, partner=%s)",
                i + 1, len(corridor_matrix),
                exporter, importer, imp_id, exp_id,
            )

            raw_records = client.fetch_corridor(imp_id, exp_id)

            if raw_records is None:
                logger.warning(
                    "No data available for %s → %s",
                    exporter, importer,
                )
                no_data += 1
            elif len(raw_records) == 0:
                logger.info(
                    "Empty response for %s → %s",
                    exporter, importer,
                )
                no_data += 1
            else:
                # Save raw response for provenance
                save_raw_response(output_dir, importer, exporter, raw_records)

                # Transform
                transformer.transform_corridor(importer, exporter, raw_records)
                successful += 1
                total_records += len(raw_records)

            # Rate limiting between requests
            if i < len(corridor_matrix) - 1:
                time.sleep(REQUEST_DELAY)

    except KeyboardInterrupt:
        logger.warning("Interrupted by user — saving partial results")
    finally:
        client.close()

    # Write output
    if transformer.lines:
        CSVWriter.write_all(output_dir, transformer)

    # Final summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("EXTRACTION COMPLETE")
    logger.info("=" * 60)
    logger.info("Corridors attempted:     %d", len(corridor_matrix))
    logger.info("Corridors with data:     %d", successful)
    logger.info("Corridors without data:  %d", no_data)
    logger.info("Total raw records:       %d", total_records)
    logger.info("Schedule headers:        %d", len(transformer.headers))
    logger.info("Schedule lines:          %d", len(transformer.lines))
    logger.info("Year rate rows:          %d", len(transformer.year_rates))
    logger.info("RoO cross-references:    %d", len(transformer.roo_crossref))
    logger.info("Output directory:        %s", output_dir)
    logger.info("=" * 60)

    return {
        "corridors_attempted": len(corridor_matrix),
        "corridors_with_data": successful,
        "corridors_without_data": no_data,
        "total_records": total_records,
        "headers": len(transformer.headers),
        "lines": len(transformer.lines),
        "year_rates": len(transformer.year_rates),
    }


# =============================================================================
# CLI
# =============================================================================

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Extract tariff elimination schedules from the UNCTAD AfCFTA "
            "e-Tariff API and transform to AIS database schema."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python extract_unctad_afcfta.py\n"
            "  python extract_unctad_afcfta.py --output-dir ./tariff_data\n"
            "  python extract_unctad_afcfta.py --corridors GHA-NGA,CMR-GHA\n"
            "  python extract_unctad_afcfta.py --dry-run\n"
            "  python extract_unctad_afcfta.py --base-year 2021 --verbose\n"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./unctad_tariff_extraction",
        help="Output directory for CSV files (default: ./unctad_tariff_extraction)",
    )
    parser.add_argument(
        "--base-year",
        type=int,
        default=DEFAULT_BASE_YEAR,
        help=f"AfCFTA implementation start year (default: {DEFAULT_BASE_YEAR})",
    )
    parser.add_argument(
        "--corridors",
        type=str,
        default=None,
        help=(
            "Comma-separated corridor pairs as EXPORTER-IMPORTER "
            "(e.g., GHA-NGA,CMR-GHA). Default: all 20 permutations."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be fetched without making API calls",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug-level logging",
    )
    return parser.parse_args()


def main():
    """Entry point."""
    args = parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info("Starting UNCTAD AfCFTA tariff extraction")
    logger.info("Output directory: %s", args.output_dir)
    logger.info("Base year: %d", args.base_year)
    if args.corridors:
        logger.info("Corridor filter: %s", args.corridors)

    result = run_extraction(
        output_dir=args.output_dir,
        base_year=args.base_year,
        corridors_filter=args.corridors,
        dry_run=args.dry_run,
    )

    if result and result.get("lines", 0) == 0 and not args.dry_run:
        logger.warning(
            "No tariff data was retrieved. This may indicate the UNCTAD API "
            "has no published schedules for the requested corridors. "
            "Try --corridors GHA-CMR,CMR-GHA which were known to work."
        )
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
