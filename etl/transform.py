"""
etl/transform.py
----------------
Transforms raw table data into clean, denormalised entity records.

Each public function accepts the full `tables` dict (from extract.py)
and returns a list of clean dicts ready for loading into SQLite.

Public API:
  transform_packages(tables)   -> list[dict]
  transform_hotels(tables)     -> list[dict]
  transform_itineraries(tables)-> list[dict]
  transform_visa(tables)       -> list[dict]
"""

from __future__ import annotations

from typing import Any

from etl.utils import get_logger, html_strip, normalize_text

logger = get_logger("etl.transform")

Tables = dict[str, list[dict[str, Any]]]


# ---------------------------------------------------------------------------
# Internal index builders
# ---------------------------------------------------------------------------

def _index_by(rows: list[dict], key: str) -> dict[str, dict]:
    """Build a dict keyed by row[key] for O(1) lookups."""
    return {row[key]: row for row in rows if row.get(key)}


def _build_region_paths(regions: list[dict]) -> dict[str, str]:
    """
    Resolve the full human-readable path for every region.

    Example: "51e5317a2e89a" -> "India > Eastern India > Sikkim"

    Uses the parent_id hierarchy in dh_regions.
    """
    by_id = _index_by(regions, "id")
    cache: dict[str, str] = {}

    def resolve(region_id: str, depth: int = 0) -> str:
        if depth > 10:
            return ""  # guard against circular references
        if region_id in cache:
            return cache[region_id]
        row = by_id.get(region_id)
        if not row:
            return ""
        title: str = normalize_text(row.get("title", ""))
        parent_id = row.get("parent_id")
        if parent_id and parent_id != region_id:
            parent_path = resolve(parent_id, depth + 1)
            # Skip the root "Regions" node in the displayed path
            if parent_path and parent_path != "Regions":
                result = f"{parent_path} > {title}"
            else:
                result = title
        else:
            result = title
        cache[region_id] = result
        return result

    for region in regions:
        resolve(region["id"])

    return cache


# ---------------------------------------------------------------------------
# Package transform
# ---------------------------------------------------------------------------

def transform_packages(tables: Tables) -> list[dict]:
    """
    Build clean package records by joining:
      dh_packages
        + dh_package_categories   (category name)
        + dh_package_types        (type tags, via dh_package_type_items)
        + dh_regions              (destination paths, via dh_package_region_items)
    """
    packages = tables.get("dh_packages", [])
    categories = tables.get("dh_package_categories", [])
    pkg_types = tables.get("dh_package_types", [])
    type_items = tables.get("dh_package_type_items", [])
    regions = tables.get("dh_regions", [])
    region_items = tables.get("dh_package_region_items", [])

    # ── Build lookup indexes ──────────────────────────────────────────────
    cat_by_id = _index_by(categories, "id")
    type_by_id = _index_by(pkg_types, "id")
    region_paths = _build_region_paths(regions)

    # package hash_id -> list of type titles
    type_map: dict[str, list[str]] = {}
    for item in type_items:
        pid = item.get("package_id", "")
        tid = item.get("package_type_id", "")
        if pid and tid and tid in type_by_id:
            type_map.setdefault(pid, []).append(
                normalize_text(type_by_id[tid].get("title", ""))
            )

    # package hash_id -> list of region path strings
    dest_map: dict[str, list[str]] = {}
    for item in region_items:
        pid = item.get("package_id", "")
        rid = item.get("package_region_id", "")
        if pid and rid:
            path = region_paths.get(rid, "")
            if path:
                dest_map.setdefault(pid, []).append(path)

    # ── Transform each package ────────────────────────────────────────────
    results: list[dict] = []
    skipped = 0

    for pkg in packages:
        # Skip inactive packages
        if str(pkg.get("status", "0")) != "1":
            skipped += 1
            continue

        hash_id: str = pkg.get("id", "")
        cat_id: str = pkg.get("category_id", "")
        category_title: str = ""
        if cat_id and cat_id in cat_by_id:
            category_title = normalize_text(
                cat_by_id[cat_id].get("title", "")
            )

        try:
            duration_days = int(pkg.get("days") or 0)
        except (ValueError, TypeError):
            duration_days = 0

        record = {
            "package_id": int(pkg.get("package_id") or 0),
            "hash_id": hash_id,
            "title": normalize_text(pkg.get("title", "")),
            "sub_title": normalize_text(pkg.get("sub_title", "")),
            "duration_days": duration_days,
            "short_description": html_strip(pkg.get("short_details")),
            "description": html_strip(pkg.get("details")),
            "category": category_title,
            "types": type_map.get(hash_id, []),
            "destinations": dest_map.get(hash_id, []),
            "is_popular": pkg.get("is_popular") == "1",
            "is_new": pkg.get("is_new") == "1",
            "is_designer": pkg.get("is_designer") == "1",
            "permalink": normalize_text(pkg.get("permalink", "")),
            "status": int(pkg.get("status") or 0),
            "created_at": pkg.get("created_at", ""),
            "modified_at": pkg.get("modified_at", ""),
        }
        results.append(record)

    logger.info(
        "Packages transformed: %d active, %d skipped (inactive)",
        len(results),
        skipped,
    )
    return results


# ---------------------------------------------------------------------------
# Hotel transform
# ---------------------------------------------------------------------------

def transform_hotels(tables: Tables) -> list[dict]:
    """
    Build clean hotel records by joining:
      dh_hotels
        + dh_regions          (region path)
        + dh_hotel_ratings    (star label)
        + dh_hotel_facilities (facility names, via dh_hotel_facility_items)
    """
    hotels = tables.get("dh_hotels", [])
    regions = tables.get("dh_regions", [])
    ratings = tables.get("dh_hotel_ratings", [])
    facilities = tables.get("dh_hotel_facilities", [])
    facility_items = tables.get("dh_hotel_facility_items", [])

    region_paths = _build_region_paths(regions)
    rating_by_id = _index_by(ratings, "id")
    facility_by_id = _index_by(facilities, "id")

    # hotel_id -> list of facility names
    fac_map: dict[str, list[str]] = {}
    for item in facility_items:
        hid = item.get("hotel_id", "")
        fid = item.get("hotel_facility_id", "")
        if hid and fid and fid in facility_by_id:
            fac_map.setdefault(hid, []).append(
                normalize_text(facility_by_id[fid].get("title", ""))
            )

    results: list[dict] = []
    skipped = 0

    for hotel in hotels:
        if str(hotel.get("status", "0")) != "1":
            skipped += 1
            continue

        rating_id = hotel.get("hotel_rating_id", "")
        rating_title = ""
        if rating_id and rating_id in rating_by_id:
            rating_title = normalize_text(
                rating_by_id[rating_id].get("title", "")
            )

        region_id = hotel.get("region_id", "")
        region_path = region_paths.get(region_id, "") if region_id else ""

        hotel_id = hotel.get("id", "")
        record = {
            "hotel_id": hotel_id,
            "name": normalize_text(hotel.get("name", "")),
            "city": normalize_text(hotel.get("city", "")),
            "address": normalize_text(hotel.get("address", "")),
            "region": region_path,
            "rating": rating_title,
            "short_description": html_strip(hotel.get("short_details")),
            "description": html_strip(hotel.get("details")),
            "facilities": fac_map.get(hotel_id, []),
            "permalink": normalize_text(hotel.get("permalink", "")),
            "status": int(hotel.get("status") or 0),
            "created_at": hotel.get("created_at", ""),
        }
        results.append(record)

    logger.info(
        "Hotels transformed: %d active, %d skipped (inactive)",
        len(results),
        skipped,
    )
    return results


# ---------------------------------------------------------------------------
# Itinerary transform
# ---------------------------------------------------------------------------

def transform_itineraries(tables: Tables) -> list[dict]:
    """
    Build clean itinerary records by denormalising package title.

      dh_itineraries + dh_packages (for title lookup)

    Only itineraries whose parent package is active (status=1) are included,
    to avoid foreign-key constraint failures on load.
    """
    itineraries = tables.get("dh_itineraries", [])
    packages = tables.get("dh_packages", [])

    # Build set of active package hash_ids and title lookup
    active_pkg_ids: set[str] = set()
    pkg_title_by_id: dict[str, str] = {}
    for p in packages:
        pid = p.get("id", "")
        if not pid:
            continue
        pkg_title_by_id[pid] = normalize_text(p.get("title", ""))
        if str(p.get("status", "0")) == "1":
            active_pkg_ids.add(pid)

    results: list[dict] = []
    skipped = 0

    for itin in itineraries:
        package_id = itin.get("package_id", "")

        # Skip itineraries whose package is inactive / missing
        if package_id not in active_pkg_ids:
            skipped += 1
            continue

        try:
            day = int(itin.get("day") or 0)
        except (ValueError, TypeError):
            day = 0

        record = {
            "itinerary_id": itin.get("id", ""),
            "package_hash_id": package_id,
            "package_title": pkg_title_by_id.get(package_id, ""),
            "day": day,
            "title": normalize_text(itin.get("title", "")),
            "details": html_strip(itin.get("details")),
            "created_at": itin.get("created_at", ""),
        }
        results.append(record)

    logger.info(
        "Itineraries transformed: %d active, %d skipped (inactive package)",
        len(results),
        skipped,
    )
    return results


# ---------------------------------------------------------------------------
# Visa transform
# ---------------------------------------------------------------------------

def transform_visa(tables: Tables) -> list[dict]:
    """
    Build clean visa records from dh_visa_services.
    """
    visa_rows = tables.get("dh_visa_services", [])
    results: list[dict] = []
    skipped = 0

    for row in visa_rows:
        if str(row.get("status", "0")) != "1":
            skipped += 1
            continue

        record = {
            "visa_id": str(row.get("id", "")),
            "country": normalize_text(row.get("title", "")),
            "requirements": html_strip(row.get("details")),
            "status": int(row.get("status") or 0),
            "created_at": row.get("created_at", ""),
        }
        results.append(record)

    logger.info(
        "Visa records transformed: %d active, %d skipped (inactive)",
        len(results),
        skipped,
    )
    return results


# ---------------------------------------------------------------------------
# Package-Hotel linking table transform
# ---------------------------------------------------------------------------

def transform_package_hotel_items(
    tables: Tables,
    active_pkg_ids: set[str],
    active_hotel_ids: set[str],
) -> list[dict]:
    """
    Build clean package-hotel link records from dh_package_hotel_items.

    Only links where both the package AND hotel are active are included.

    Args:
        active_pkg_ids:   set of hash_ids for active packages
        active_hotel_ids: set of hotel_ids for active hotels
    """
    raw_items = tables.get("dh_package_hotel_items", [])
    results: list[dict] = []
    skipped = 0

    for item in raw_items:
        pid = item.get("package_id", "")
        hid = item.get("hotel_id", "")

        if not pid or not hid:
            skipped += 1
            continue
        if pid not in active_pkg_ids or hid not in active_hotel_ids:
            skipped += 1
            continue

        try:
            sort_order = int(item.get("sort_order") or 0)
        except (ValueError, TypeError):
            sort_order = 0

        results.append({
            "package_hash_id": pid,
            "hotel_id": hid,
            "sort_order": sort_order,
        })

    logger.info(
        "Package-hotel links transformed: %d active, %d skipped",
        len(results),
        skipped,
    )
    return results
