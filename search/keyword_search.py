"""
search/keyword_search.py
------------------------
SQLite FTS5-powered keyword search across packages, hotels,
itineraries, and visa records.

All searches use BM25 ranking (native to FTS5) so the most relevant
results surface first.

Public API:
  search_all(query, db_path, limit)      -> SearchResults
  search_packages(query, db_path, limit) -> list[PackageResult]
  search_hotels(query, db_path, limit)   -> list[HotelResult]
  search_visa(query, db_path, limit)     -> list[VisaResult]

Usage:
  from search.keyword_search import search_all
  results = search_all("Kerala family trip", db_path="db/travel.db")
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass, field
from typing import Any

DEFAULT_DB_PATH = os.environ.get("SQLITE_DB_PATH", "db/travel.db")
DEFAULT_LIMIT = 10


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class PackageResult:
    package_id: int
    hash_id: str
    title: str
    sub_title: str
    duration_days: int
    short_description: str
    category: str
    types: list[str]
    destinations: list[str]
    is_popular: bool
    permalink: str
    score: float
    result_type: str = "package"


@dataclass
class HotelResult:
    hotel_id: str
    name: str
    city: str
    region: str
    rating: str
    short_description: str
    facilities: list[str]
    permalink: str
    score: float
    result_type: str = "hotel"


@dataclass
class VisaResult:
    visa_id: str
    country: str
    requirements: str       # truncated snippet
    score: float
    result_type: str = "visa"


@dataclass
class ItineraryResult:
    itinerary_id: str
    package_title: str
    package_hash_id: str
    day: int
    title: str
    details: str            # truncated snippet
    score: float
    result_type: str = "itinerary"


@dataclass
class SearchResults:
    query: str
    packages: list[PackageResult] = field(default_factory=list)
    hotels: list[HotelResult] = field(default_factory=list)
    visa: list[VisaResult] = field(default_factory=list)
    itineraries: list[ItineraryResult] = field(default_factory=list)
    total: int = 0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_connection(db_path: str) -> sqlite3.Connection:
    if not os.path.exists(db_path):
        raise FileNotFoundError(
            f"Database not found: {db_path}. Run 'python run_etl.py' first."
        )
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _split_pipe(value: str | None) -> list[str]:
    """Split a pipe-separated string back into a list."""
    if not value:
        return []
    return [v.strip() for v in value.split("|") if v.strip()]


def _snippet(text: str, max_len: int = 300) -> str:
    """Return a truncated snippet of *text*."""
    if not text:
        return ""
    return text[:max_len] + ("…" if len(text) > max_len else "")


def _sanitize_query(query: str) -> str:
    """
    Make the query safe for FTS5 MATCH expressions.

    - Strips characters that would cause FTS5 parse errors
    - Wraps multi-word queries so each word is searched independently
    - Falls back to prefix search: each word becomes  word*
    """
    import re
    # Remove FTS5 special characters except alphanumerics and spaces
    clean = re.sub(r'[^\w\s]', ' ', query, flags=re.UNICODE)
    words = clean.split()
    if not words:
        return '""'  # empty match — returns nothing
    # Use prefix matching so "Keral" matches "Kerala"
    return " ".join(f"{w}*" for w in words)


# ---------------------------------------------------------------------------
# Per-entity search functions
# ---------------------------------------------------------------------------

def search_packages(
    query: str,
    db_path: str = DEFAULT_DB_PATH,
    limit: int = DEFAULT_LIMIT,
) -> list[PackageResult]:
    """
    Search packages using FTS5 BM25 ranking.

    Searches: title, sub_title, short_description, description,
              category, types, destinations.
    """
    fts_query = _sanitize_query(query)
    sql = """
        SELECT
            p.package_id,
            p.hash_id,
            p.title,
            p.sub_title,
            p.duration_days,
            p.short_description,
            p.category,
            p.types,
            p.destinations,
            p.is_popular,
            p.permalink,
            bm25(packages_fts) AS score
        FROM packages_fts
        JOIN packages p ON packages_fts.rowid = p.package_id
        WHERE packages_fts MATCH ?
        ORDER BY score
        LIMIT ?
    """
    conn = _get_connection(db_path)
    try:
        rows = conn.execute(sql, (fts_query, limit)).fetchall()
        return [
            PackageResult(
                package_id=row["package_id"],
                hash_id=row["hash_id"],
                title=row["title"],
                sub_title=row["sub_title"] or "",
                duration_days=row["duration_days"] or 0,
                short_description=row["short_description"] or "",
                category=row["category"] or "",
                types=_split_pipe(row["types"]),
                destinations=_split_pipe(row["destinations"]),
                is_popular=bool(row["is_popular"]),
                permalink=row["permalink"] or "",
                score=row["score"],
            )
            for row in rows
        ]
    finally:
        conn.close()


def search_hotels(
    query: str,
    db_path: str = DEFAULT_DB_PATH,
    limit: int = DEFAULT_LIMIT,
) -> list[HotelResult]:
    """
    Search hotels using FTS5 BM25 ranking.

    Searches: name, city, region, description, facilities, rating.
    """
    fts_query = _sanitize_query(query)
    sql = """
        SELECT
            h.hotel_id,
            h.name,
            h.city,
            h.region,
            h.rating,
            h.short_description,
            h.facilities,
            h.permalink,
            bm25(hotels_fts) AS score
        FROM hotels_fts
        JOIN hotels h ON hotels_fts.rowid = h.rowid
        WHERE hotels_fts MATCH ?
        ORDER BY score
        LIMIT ?
    """
    conn = _get_connection(db_path)
    try:
        rows = conn.execute(sql, (fts_query, limit)).fetchall()
        return [
            HotelResult(
                hotel_id=row["hotel_id"],
                name=row["name"],
                city=row["city"] or "",
                region=row["region"] or "",
                rating=row["rating"] or "",
                short_description=row["short_description"] or "",
                facilities=_split_pipe(row["facilities"]),
                permalink=row["permalink"] or "",
                score=row["score"],
            )
            for row in rows
        ]
    finally:
        conn.close()


def search_visa(
    query: str,
    db_path: str = DEFAULT_DB_PATH,
    limit: int = DEFAULT_LIMIT,
) -> list[VisaResult]:
    """Search visa records by country name or requirement keywords."""
    fts_query = _sanitize_query(query)
    sql = """
        SELECT
            v.visa_id,
            v.country,
            v.requirements,
            bm25(visa_fts) AS score
        FROM visa_fts
        JOIN visa v ON visa_fts.rowid = v.rowid
        WHERE visa_fts MATCH ?
        ORDER BY score
        LIMIT ?
    """
    conn = _get_connection(db_path)
    try:
        rows = conn.execute(sql, (fts_query, limit)).fetchall()
        return [
            VisaResult(
                visa_id=row["visa_id"],
                country=row["country"],
                requirements=_snippet(row["requirements"], 400),
                score=row["score"],
            )
            for row in rows
        ]
    finally:
        conn.close()


def search_itineraries(
    query: str,
    db_path: str = DEFAULT_DB_PATH,
    limit: int = DEFAULT_LIMIT,
) -> list[ItineraryResult]:
    """Search itinerary entries by day title or activity details."""
    fts_query = _sanitize_query(query)
    sql = """
        SELECT
            i.itinerary_id,
            i.package_title,
            i.package_hash_id,
            i.day,
            i.title,
            i.details,
            bm25(itineraries_fts) AS score
        FROM itineraries_fts
        JOIN itineraries i ON itineraries_fts.rowid = i.rowid
        WHERE itineraries_fts MATCH ?
        ORDER BY score
        LIMIT ?
    """
    conn = _get_connection(db_path)
    try:
        rows = conn.execute(sql, (fts_query, limit)).fetchall()
        return [
            ItineraryResult(
                itinerary_id=row["itinerary_id"],
                package_title=row["package_title"] or "",
                package_hash_id=row["package_hash_id"],
                day=row["day"] or 0,
                title=row["title"] or "",
                details=_snippet(row["details"], 300),
                score=row["score"],
            )
            for row in rows
        ]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Unified search
# ---------------------------------------------------------------------------

def search_all(
    query: str,
    db_path: str = DEFAULT_DB_PATH,
    limit: int = DEFAULT_LIMIT,
) -> SearchResults:
    """
    Run the query across all entity types and return a unified result.

    Each entity type is searched independently and results are returned
    in separate lists. Frontend can merge and display as needed.

    Example:
        results = search_all("Kerala family trip")
        # results.packages -> Kerala packages
        # results.hotels   -> hotels in Kerala
        # results.visa     -> not much (visa is country-based)
    """
    results = SearchResults(query=query)
    results.packages = search_packages(query, db_path, limit)
    results.hotels = search_hotels(query, db_path, limit)
    results.visa = search_visa(query, db_path, limit)
    results.itineraries = search_itineraries(query, db_path, limit)
    results.total = (
        len(results.packages)
        + len(results.hotels)
        + len(results.visa)
        + len(results.itineraries)
    )
    return results
