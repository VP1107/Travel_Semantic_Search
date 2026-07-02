"""
etl/load.py
-----------
Loads transformed data into:
  1. data/processed/*.json  (processed copies, source never touched)
  2. db/travel.db           (SQLite with FTS5 for keyword search)

Public API:
  save_processed_json(entities, output_dir) -> None
  load_sqlite(entities, db_path, schema_path) -> None
"""

from __future__ import annotations

import json
import os
import sqlite3
from typing import Any

from etl.utils import get_logger

logger = get_logger("etl.load")

# Entity name -> file name mapping
ENTITY_FILES = {
    "packages": "packages.json",
    "hotels": "hotels.json",
    "itineraries": "itineraries.json",
    "visa": "visa.json",
}

# Fields whose values are lists and must be serialized as pipe-separated strings
# when writing to SQLite (FTS5 tokenizes them naturally)
LIST_FIELDS = {"types", "destinations", "facilities"}


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------

def save_processed_json(
    entities: dict[str, list[dict[str, Any]]],
    output_dir: str,
) -> None:
    """
    Write each entity list to a separate JSON file in *output_dir*.

    Existing files are overwritten so re-running ETL always produces
    a fresh, consistent snapshot.
    """
    os.makedirs(output_dir, exist_ok=True)

    for entity_name, rows in entities.items():
        filename = ENTITY_FILES.get(entity_name, f"{entity_name}.json")
        out_path = os.path.join(output_dir, filename)

        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(rows, fh, ensure_ascii=False, indent=2)

        logger.info(
            "Written %s: %d records -> %s",
            entity_name,
            len(rows),
            out_path,
        )


# ---------------------------------------------------------------------------
# SQLite load
# ---------------------------------------------------------------------------

def _pipe(values: list[str]) -> str:
    """Convert a list to a pipe-separated string for SQLite storage."""
    return " | ".join(v for v in values if v)


def load_sqlite(
    entities: dict[str, list[dict[str, Any]]],
    db_path: str,
    schema_path: str,
) -> None:
    """
    Create (or recreate) the SQLite database at *db_path* and populate it.

    Steps:
      1. Drop and recreate the database file for a clean load
      2. Apply schema.sql
      3. Insert packages, hotels, itineraries, visa in order
    """
    # Ensure parent directory exists
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    # Remove stale DB for clean rebuild
    if os.path.exists(db_path):
        os.remove(db_path)
        logger.info("Removed existing database: %s", db_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Load and apply schema
    logger.info("Applying schema: %s", schema_path)
    with open(schema_path, "r", encoding="utf-8") as fh:
        schema_sql = fh.read()
    conn.executescript(schema_sql)
    conn.commit()

    # ── Insert packages ─────────────────────────────────────────────────
    packages = entities.get("packages", [])
    _insert_packages(cur, packages)
    logger.info("Inserted %d packages", len(packages))

    # ── Insert hotels ───────────────────────────────────────────────────
    hotels = entities.get("hotels", [])
    _insert_hotels(cur, hotels)
    logger.info("Inserted %d hotels", len(hotels))

    # ── Insert itineraries ──────────────────────────────────────────────
    itineraries = entities.get("itineraries", [])
    _insert_itineraries(cur, itineraries)
    logger.info("Inserted %d itineraries", len(itineraries))

    # ── Insert visa ─────────────────────────────────────────────────────
    visa = entities.get("visa", [])
    _insert_visa(cur, visa)
    logger.info("Inserted %d visa records", len(visa))

    # ── Insert package-hotel links ────────────────────────────────────────
    pkg_hotel_items = entities.get("package_hotel_items", [])
    _insert_package_hotel_items(cur, pkg_hotel_items)
    logger.info("Inserted %d package-hotel links", len(pkg_hotel_items))

    conn.commit()
    conn.close()
    logger.info("Database ready: %s", db_path)


# ---------------------------------------------------------------------------
# Entity-specific insert helpers
# ---------------------------------------------------------------------------

def _insert_packages(cur: sqlite3.Cursor, packages: list[dict]) -> None:
    sql = """
        INSERT INTO packages (
            package_id, hash_id, title, sub_title, duration_days,
            short_description, description, category, types, destinations,
            is_popular, is_new, is_designer, permalink, status,
            created_at, modified_at
        ) VALUES (
            :package_id, :hash_id, :title, :sub_title, :duration_days,
            :short_description, :description, :category, :types, :destinations,
            :is_popular, :is_new, :is_designer, :permalink, :status,
            :created_at, :modified_at
        )
    """
    rows = []
    for p in packages:
        row = dict(p)
        row["types"] = _pipe(p.get("types", []))
        row["destinations"] = _pipe(p.get("destinations", []))
        row["is_popular"] = int(p.get("is_popular", False))
        row["is_new"] = int(p.get("is_new", False))
        row["is_designer"] = int(p.get("is_designer", False))
        rows.append(row)
    cur.executemany(sql, rows)


def _insert_hotels(cur: sqlite3.Cursor, hotels: list[dict]) -> None:
    sql = """
        INSERT INTO hotels (
            hotel_id, name, city, address, region, rating,
            short_description, description, facilities, permalink,
            status, created_at
        ) VALUES (
            :hotel_id, :name, :city, :address, :region, :rating,
            :short_description, :description, :facilities, :permalink,
            :status, :created_at
        )
    """
    rows = []
    for h in hotels:
        row = dict(h)
        row["facilities"] = _pipe(h.get("facilities", []))
        rows.append(row)
    cur.executemany(sql, rows)


def _insert_itineraries(cur: sqlite3.Cursor, itineraries: list[dict]) -> None:
    sql = """
        INSERT INTO itineraries (
            itinerary_id, package_hash_id, package_title,
            day, title, details, created_at
        ) VALUES (
            :itinerary_id, :package_hash_id, :package_title,
            :day, :title, :details, :created_at
        )
    """
    cur.executemany(sql, itineraries)


def _insert_visa(cur: sqlite3.Cursor, visa: list[dict]) -> None:
    sql = """
        INSERT INTO visa (
            visa_id, country, requirements, status, created_at
        ) VALUES (
            :visa_id, :country, :requirements, :status, :created_at
        )
    """
    cur.executemany(sql, visa)


def _insert_package_hotel_items(
    cur: sqlite3.Cursor, items: list[dict]
) -> None:
    sql = """
        INSERT OR IGNORE INTO package_hotel_items
            (package_hash_id, hotel_id, sort_order)
        VALUES
            (:package_hash_id, :hotel_id, :sort_order)
    """
    cur.executemany(sql, items)
