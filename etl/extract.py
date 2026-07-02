"""
etl/extract.py
--------------
Loads the raw PHPMyAdmin JSON export and splits it into named tables.

Public API:
  load_tables(json_path) -> dict[str, list[dict]]
      Returns every table as a list of row-dicts, keyed by table name.
      Raises FileNotFoundError / ValueError on bad input.
"""

import json
import os
from typing import Any

from etl.utils import get_logger

logger = get_logger("etl.extract")

# Tables we expect to find — used for validation warnings only
EXPECTED_TABLES = {
    "dh_packages",
    "dh_hotels",
    "dh_itineraries",
    "dh_visa_services",
    "dh_regions",
    "dh_package_categories",
    "dh_package_types",
    "dh_package_region_items",
    "dh_package_hotel_items",
    "dh_package_type_items",
    "dh_package_tab_items",
    "dh_tabs",
    "dh_hotel_ratings",
    "dh_hotel_facilities",
    "dh_hotel_facility_items",
}


def load_tables(json_path: str) -> dict[str, list[dict[str, Any]]]:
    """
    Parse the PHPMyAdmin JSON export at *json_path*.

    Returns a mapping of table_name -> list of row dicts.
    Rows are returned exactly as stored — no transformation here.

    Raises:
        FileNotFoundError  : if json_path does not exist
        ValueError         : if the file is not a valid JSON array
    """
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"Source file not found: {json_path}")

    logger.info("Loading source file: %s", json_path)
    file_size_mb = os.path.getsize(json_path) / (1024 * 1024)
    logger.info("File size: %.2f MB", file_size_mb)

    with open(json_path, "r", encoding="utf-8") as fh:
        raw: Any = json.load(fh)

    if not isinstance(raw, list):
        raise ValueError(
            f"Expected top-level JSON array, got {type(raw).__name__}"
        )

    logger.info("Top-level entries in export: %d", len(raw))

    tables: dict[str, list[dict[str, Any]]] = {}

    for entry in raw:
        if not isinstance(entry, dict):
            continue
        if entry.get("type") != "table":
            continue

        name: str = entry.get("name", "")
        rows: list[dict] = entry.get("data", [])

        if not name:
            logger.warning("Skipping unnamed table entry")
            continue

        tables[name] = rows
        logger.debug("  Loaded table %-45s  rows=%d", name, len(rows))

    logger.info("Tables extracted: %d", len(tables))

    # Warn about any expected tables that are missing
    for expected in sorted(EXPECTED_TABLES):
        if expected not in tables:
            logger.warning("Expected table not found: %s", expected)

    return tables
