"""
run_etl.py
----------
CLI entry point for the full ETL pipeline.

Usage:
    python run_etl.py

Environment variables (or .env):
    SOURCE_JSON        Path to source JSON export  (default: destissp_portal.json)
    PROCESSED_DATA_DIR Output directory for JSON   (default: data/processed)
    SQLITE_DB_PATH     Path for SQLite database    (default: db/travel.db)
    LOG_FILE           Path for log file           (default: logs/etl.log)
"""

import os
import sys
import time

# Load .env if present (optional — falls back to shell env)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed; use shell env

from etl.extract import load_tables
from etl.load import load_sqlite, save_processed_json
from etl.transform import (
    transform_hotels,
    transform_itineraries,
    transform_packages,
    transform_package_hotel_items,
    transform_visa,
)
from etl.utils import get_logger

logger = get_logger("etl.runner")


def main() -> int:
    """
    Run the complete ETL pipeline.

    Returns 0 on success, 1 on failure.
    """
    start_time = time.time()

    # ── Configuration ────────────────────────────────────────────────────
    source_json = os.environ.get("SOURCE_JSON", "destissp_portal.json")
    processed_dir = os.environ.get("PROCESSED_DATA_DIR", "data/processed")
    db_path = os.environ.get("SQLITE_DB_PATH", "db/travel.db")
    schema_path = os.path.join("db", "schema.sql")

    logger.info("=" * 60)
    logger.info("Travel Search ETL Pipeline — starting")
    logger.info("=" * 60)
    logger.info("Source JSON : %s", source_json)
    logger.info("Processed   : %s", processed_dir)
    logger.info("SQLite DB   : %s", db_path)

    # ── Step 1: Extract ──────────────────────────────────────────────────
    logger.info("-" * 40)
    logger.info("STEP 1/4  Extract")
    try:
        tables = load_tables(source_json)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Extract failed: %s", exc)
        return 1

    # ── Step 2: Transform ────────────────────────────────────────────────
    logger.info("-" * 40)
    logger.info("STEP 2/4  Transform")

    packages = transform_packages(tables)
    hotels = transform_hotels(tables)
    itineraries = transform_itineraries(tables)
    visa = transform_visa(tables)

    # Build active ID sets for FK-safe linking table
    active_pkg_ids = {p["hash_id"] for p in packages}
    active_hotel_ids = {h["hotel_id"] for h in hotels}
    pkg_hotel_items = transform_package_hotel_items(
        tables, active_pkg_ids, active_hotel_ids
    )

    entities = {
        "packages": packages,
        "hotels": hotels,
        "itineraries": itineraries,
        "visa": visa,
        "package_hotel_items": pkg_hotel_items,
    }

    # ── Step 3: Save processed JSON ──────────────────────────────────────
    logger.info("-" * 40)
    logger.info("STEP 3/4  Save processed JSON")
    try:
        save_processed_json(entities, processed_dir)
    except OSError as exc:
        logger.error("JSON save failed: %s", exc)
        return 1

    # ── Step 4: Load SQLite ──────────────────────────────────────────────
    logger.info("-" * 40)
    logger.info("STEP 4/4  Load SQLite")
    try:
        load_sqlite(entities, db_path, schema_path)
    except Exception as exc:
        logger.error("SQLite load failed: %s", exc)
        return 1

    # ── Summary ──────────────────────────────────────────────────────────
    elapsed = time.time() - start_time
    logger.info("=" * 60)
    logger.info("ETL complete in %.2fs", elapsed)
    logger.info("  Packages    : %d", len(packages))
    logger.info("  Hotels      : %d", len(hotels))
    logger.info("  Itineraries : %d", len(itineraries))
    logger.info("  Visa        : %d", len(visa))
    logger.info("  Hotel links : %d", len(pkg_hotel_items))
    logger.info("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
