"""
search/semantic_search.py
--------------------------
Semantic search using ChromaDB vector similarity.

Encodes the user query with all-MiniLM-L6-v2, queries each ChromaDB
collection, and enriches results with full records from SQLite.

Distance interpretation (cosine, L2-normalised vectors):
    0.0  = identical
    ~0.5 = related
    ~1.0 = unrelated
    2.0  = opposite

Public API:
    semantic_search_all(query, ...)         -> SemanticResults
    semantic_search_packages(query, ...)    -> list[SemanticPackageResult]
    semantic_search_hotels(query, ...)      -> list[SemanticHotelResult]
    semantic_search_itineraries(query, ...) -> list[SemanticItineraryResult]
    semantic_search_visa(query, ...)        -> list[SemanticVisaResult]
"""

from __future__ import annotations

import logging
import os
import sqlite3
from dataclasses import dataclass, field
from typing import Any

import chromadb

from embeddings.embedder import get_embedder
from ingest.chroma_ingest import (
    COLLECTION_HOTELS,
    COLLECTION_ITINERARIES,
    COLLECTION_PACKAGES,
    COLLECTION_VISA,
)

logger = logging.getLogger("search.semantic")

DEFAULT_DB_PATH     = os.environ.get("SQLITE_DB_PATH", "db/travel.db")
DEFAULT_CHROMA_PATH = os.environ.get("CHROMA_DB_PATH", "db/chroma")
DEFAULT_N_RESULTS   = 10

# Relevance threshold — results with distance > this are considered noise
# Tuned for all-MiniLM-L6-v2 cosine distance on travel data
DISTANCE_THRESHOLD = 1.4


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class SemanticPackageResult:
    package_id: int
    hash_id: str
    title: str
    sub_title: str
    duration_days: int
    category: str
    types: list[str]
    destinations: list[str]
    is_popular: bool
    permalink: str
    short_description: str
    distance: float
    result_type: str = "package"
    search_type: str = "semantic"


@dataclass
class SemanticHotelResult:
    hotel_id: str
    name: str
    city: str
    region: str
    rating: str
    facilities: list[str]
    permalink: str
    short_description: str
    distance: float
    result_type: str = "hotel"
    search_type: str = "semantic"


@dataclass
class SemanticItineraryResult:
    itinerary_id: str
    package_hash_id: str
    package_title: str
    day: int
    title: str
    details_snippet: str
    distance: float
    result_type: str = "itinerary"
    search_type: str = "semantic"


@dataclass
class SemanticVisaResult:
    visa_id: str
    country: str
    requirements_snippet: str
    distance: float
    result_type: str = "visa"
    search_type: str = "semantic"


@dataclass
class SemanticResults:
    query: str
    packages: list[SemanticPackageResult] = field(default_factory=list)
    hotels: list[SemanticHotelResult] = field(default_factory=list)
    itineraries: list[SemanticItineraryResult] = field(default_factory=list)
    visa: list[SemanticVisaResult] = field(default_factory=list)
    total: int = 0
    search_type: str = "semantic"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_chroma_client(chroma_path: str) -> chromadb.PersistentClient:
    if not os.path.exists(chroma_path):
        raise FileNotFoundError(
            f"ChromaDB not found at: {chroma_path}\n"
            "Run 'python run_ingest.py' first to populate the vector store."
        )
    return chromadb.PersistentClient(path=chroma_path)


def _get_sqlite(db_path: str) -> sqlite3.Connection:
    if not os.path.exists(db_path):
        raise FileNotFoundError(
            f"SQLite database not found: {db_path}\n"
            "Run 'python run_etl.py' first."
        )
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _split_pipe(value: str | None) -> list[str]:
    if not value:
        return []
    return [v.strip() for v in value.split("|") if v.strip()]


def _query_collection(
    client: chromadb.PersistentClient,
    collection_name: str,
    query_embedding: list[float],
    n_results: int,
) -> dict[str, Any]:
    """
    Query a ChromaDB collection and return the raw results dict.
    Returns empty structure if collection is missing or query fails.
    """
    try:
        col = client.get_collection(collection_name)
        results = col.query(
            query_embeddings=[query_embedding],
            n_results=min(n_results, col.count()),
            include=["metadatas", "distances", "documents"],
        )
        return results
    except Exception as exc:
        logger.warning("ChromaDB query failed [%s]: %s", collection_name, exc)
        return {"ids": [[]], "metadatas": [[]], "distances": [[]], "documents": [[]]}


def _filter_by_threshold(
    results: dict[str, Any],
    threshold: float = DISTANCE_THRESHOLD,
) -> list[tuple[str, dict, float]]:
    """
    Extract (id, metadata, distance) tuples from raw ChromaDB results,
    filtered to only include results below the distance threshold.
    """
    ids = results.get("ids", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    dists = results.get("distances", [[]])[0]

    return [
        (rid, meta, dist)
        for rid, meta, dist in zip(ids, metas, dists)
        if dist <= threshold
    ]


# ---------------------------------------------------------------------------
# Per-entity semantic search
# ---------------------------------------------------------------------------

def semantic_search_packages(
    query: str,
    chroma_path: str = DEFAULT_CHROMA_PATH,
    n_results: int = DEFAULT_N_RESULTS,
) -> list[SemanticPackageResult]:
    """
    Semantic search over travel packages.

    Uses ChromaDB metadata directly — no SQLite round-trip needed for summaries.
    """
    embedder = get_embedder()
    query_vec = embedder.encode_one(query)
    client = _get_chroma_client(chroma_path)

    raw = _query_collection(client, COLLECTION_PACKAGES, query_vec, n_results)
    hits = _filter_by_threshold(raw)

    results = []
    for _, meta, dist in hits:
        results.append(
            SemanticPackageResult(
                package_id=int(meta.get("package_id") or 0),
                hash_id=str(meta.get("hash_id", "")),
                title=str(meta.get("title", "")),
                sub_title=str(meta.get("sub_title", "")),
                duration_days=int(meta.get("duration_days") or 0),
                category=str(meta.get("category", "")),
                types=_split_pipe(meta.get("types")),
                destinations=_split_pipe(meta.get("destinations")),
                is_popular=bool(int(meta.get("is_popular") or 0)),
                permalink=str(meta.get("permalink", "")),
                short_description=str(meta.get("short_description", "")),
                distance=round(dist, 4),
            )
        )
    return results


def semantic_search_hotels(
    query: str,
    chroma_path: str = DEFAULT_CHROMA_PATH,
    n_results: int = DEFAULT_N_RESULTS,
) -> list[SemanticHotelResult]:
    """Semantic search over hotels."""
    embedder = get_embedder()
    query_vec = embedder.encode_one(query)
    client = _get_chroma_client(chroma_path)

    raw = _query_collection(client, COLLECTION_HOTELS, query_vec, n_results)
    hits = _filter_by_threshold(raw)

    results = []
    for _, meta, dist in hits:
        results.append(
            SemanticHotelResult(
                hotel_id=str(meta.get("hotel_id", "")),
                name=str(meta.get("name", "")),
                city=str(meta.get("city", "")),
                region=str(meta.get("region", "")),
                rating=str(meta.get("rating", "")),
                facilities=_split_pipe(meta.get("facilities")),
                permalink=str(meta.get("permalink", "")),
                short_description=str(meta.get("short_description", "")),
                distance=round(dist, 4),
            )
        )
    return results


def semantic_search_itineraries(
    query: str,
    chroma_path: str = DEFAULT_CHROMA_PATH,
    n_results: int = DEFAULT_N_RESULTS,
) -> list[SemanticItineraryResult]:
    """Semantic search over itinerary entries."""
    embedder = get_embedder()
    query_vec = embedder.encode_one(query)
    client = _get_chroma_client(chroma_path)

    raw = _query_collection(client, COLLECTION_ITINERARIES, query_vec, n_results)
    hits = _filter_by_threshold(raw)

    results = []
    for _, meta, dist in hits:
        results.append(
            SemanticItineraryResult(
                itinerary_id=str(meta.get("itinerary_id", "")),
                package_hash_id=str(meta.get("package_hash_id", "")),
                package_title=str(meta.get("package_title", "")),
                day=int(meta.get("day") or 0),
                title=str(meta.get("title", "")),
                details_snippet=str(meta.get("details_snippet", "")),
                distance=round(dist, 4),
            )
        )
    return results


def semantic_search_visa(
    query: str,
    chroma_path: str = DEFAULT_CHROMA_PATH,
    n_results: int = DEFAULT_N_RESULTS,
) -> list[SemanticVisaResult]:
    """Semantic search over visa records."""
    embedder = get_embedder()
    query_vec = embedder.encode_one(query)
    client = _get_chroma_client(chroma_path)

    raw = _query_collection(client, COLLECTION_VISA, query_vec, n_results)
    hits = _filter_by_threshold(raw)

    results = []
    for _, meta, dist in hits:
        results.append(
            SemanticVisaResult(
                visa_id=str(meta.get("visa_id", "")),
                country=str(meta.get("country", "")),
                requirements_snippet=str(meta.get("requirements_snippet", "")),
                distance=round(dist, 4),
            )
        )
    return results


# ---------------------------------------------------------------------------
# Unified semantic search
# ---------------------------------------------------------------------------

def semantic_search_all(
    query: str,
    chroma_path: str = DEFAULT_CHROMA_PATH,
    n_results: int = DEFAULT_N_RESULTS,
    include_types: set[str] | None = None,
) -> SemanticResults:
    """
    Run semantic search across all entity types.

    Args:
        query:         Natural language search query
        chroma_path:   Path to ChromaDB persistent storage
        n_results:     Max results per entity type
        include_types: Optional set of entity types to include.
                       e.g. {"packages", "hotels"} to skip itineraries + visa.
                       None = include all.

    Returns:
        SemanticResults with per-type result lists.

    Example:
        results = semantic_search_all("romantic beach sunset holiday")
        # results.packages -> Goa, Maldives, Kerala beach packages
        # results.hotels   -> beachfront luxury resorts
    """
    if include_types is None:
        include_types = {"packages", "hotels", "itineraries", "visa"}

    # Encode query ONCE — reuse across all collections
    embedder = get_embedder()
    query_vec = embedder.encode_one(query)
    client = _get_chroma_client(chroma_path)

    out = SemanticResults(query=query)

    if "packages" in include_types:
        raw = _query_collection(client, COLLECTION_PACKAGES, query_vec, n_results)
        for _, meta, dist in _filter_by_threshold(raw):
            out.packages.append(
                SemanticPackageResult(
                    package_id=int(meta.get("package_id") or 0),
                    hash_id=str(meta.get("hash_id", "")),
                    title=str(meta.get("title", "")),
                    sub_title=str(meta.get("sub_title", "")),
                    duration_days=int(meta.get("duration_days") or 0),
                    category=str(meta.get("category", "")),
                    types=_split_pipe(meta.get("types")),
                    destinations=_split_pipe(meta.get("destinations")),
                    is_popular=bool(int(meta.get("is_popular") or 0)),
                    permalink=str(meta.get("permalink", "")),
                    short_description=str(meta.get("short_description", "")),
                    distance=round(dist, 4),
                )
            )

    if "hotels" in include_types:
        raw = _query_collection(client, COLLECTION_HOTELS, query_vec, n_results)
        for _, meta, dist in _filter_by_threshold(raw):
            out.hotels.append(
                SemanticHotelResult(
                    hotel_id=str(meta.get("hotel_id", "")),
                    name=str(meta.get("name", "")),
                    city=str(meta.get("city", "")),
                    region=str(meta.get("region", "")),
                    rating=str(meta.get("rating", "")),
                    facilities=_split_pipe(meta.get("facilities")),
                    permalink=str(meta.get("permalink", "")),
                    short_description=str(meta.get("short_description", "")),
                    distance=round(dist, 4),
                )
            )

    if "itineraries" in include_types:
        raw = _query_collection(client, COLLECTION_ITINERARIES, query_vec, n_results)
        for _, meta, dist in _filter_by_threshold(raw):
            out.itineraries.append(
                SemanticItineraryResult(
                    itinerary_id=str(meta.get("itinerary_id", "")),
                    package_hash_id=str(meta.get("package_hash_id", "")),
                    package_title=str(meta.get("package_title", "")),
                    day=int(meta.get("day") or 0),
                    title=str(meta.get("title", "")),
                    details_snippet=str(meta.get("details_snippet", "")),
                    distance=round(dist, 4),
                )
            )

    if "visa" in include_types:
        raw = _query_collection(client, COLLECTION_VISA, query_vec, n_results)
        for _, meta, dist in _filter_by_threshold(raw):
            out.visa.append(
                SemanticVisaResult(
                    visa_id=str(meta.get("visa_id", "")),
                    country=str(meta.get("country", "")),
                    requirements_snippet=str(meta.get("requirements_snippet", "")),
                    distance=round(dist, 4),
                )
            )

    out.total = (
        len(out.packages)
        + len(out.hotels)
        + len(out.itineraries)
        + len(out.visa)
    )
    return out
