"""
search/hybrid_search.py
-----------------------
Hybrid search: fuses FTS5 keyword results + ChromaDB semantic results
using Reciprocal Rank Fusion (RRF).

Why RRF?
    RRF(d) = Σ 1 / (k + rank_i(d))
    k=60 (standard constant that dampens high-rank advantage)

    - Parameter-free: no score normalisation needed across different scales
    - Robust: outperforms weighted linear combinations without calibration
    - Proven: used by Elasticsearch, Vespa, and major IR systems

How it works:
    1. Keyword search → ordered list of results (BM25)
    2. Semantic search → ordered list of results (cosine distance)
    3. Each result gets an RRF score based on its rank in each list
    4. Scores are summed → final merged ranking
    5. Results enriched with rank_source metadata (keyword/semantic/both)

Public API:
    hybrid_search_all(query, ...) -> HybridResults
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

from search.keyword_search import (
    search_hotels as kw_hotels,
    search_itineraries as kw_itineraries,
    search_packages as kw_packages,
    search_visa as kw_visa,
)
from search.semantic_search import (
    semantic_search_hotels,
    semantic_search_itineraries,
    semantic_search_packages,
    semantic_search_visa,
)

logger = logging.getLogger("search.hybrid")

DEFAULT_DB_PATH     = os.environ.get("SQLITE_DB_PATH", "db/travel.db")
DEFAULT_CHROMA_PATH = os.environ.get("CHROMA_DB_PATH", "db/chroma")
RRF_K = 60  # Standard constant — do not change without benchmarking


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class HybridPackageResult:
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
    rrf_score: float
    rank_source: str          # "keyword", "semantic", or "both"
    result_type: str = "package"
    search_type: str = "hybrid"


@dataclass
class HybridHotelResult:
    hotel_id: str
    name: str
    city: str
    region: str
    rating: str
    facilities: list[str]
    permalink: str
    short_description: str
    rrf_score: float
    rank_source: str
    result_type: str = "hotel"
    search_type: str = "hybrid"


@dataclass
class HybridItineraryResult:
    itinerary_id: str
    package_hash_id: str
    package_title: str
    day: int
    title: str
    details_snippet: str
    rrf_score: float
    rank_source: str
    result_type: str = "itinerary"
    search_type: str = "hybrid"


@dataclass
class HybridVisaResult:
    visa_id: str
    country: str
    requirements_snippet: str
    rrf_score: float
    rank_source: str
    result_type: str = "visa"
    search_type: str = "hybrid"


@dataclass
class HybridResults:
    query: str
    packages: list[HybridPackageResult] = field(default_factory=list)
    hotels: list[HybridHotelResult] = field(default_factory=list)
    itineraries: list[HybridItineraryResult] = field(default_factory=list)
    visa: list[HybridVisaResult] = field(default_factory=list)
    total: int = 0
    search_type: str = "hybrid"


# ---------------------------------------------------------------------------
# RRF core
# ---------------------------------------------------------------------------

def _rrf_score(rank: int, k: int = RRF_K) -> float:
    """Compute the RRF score for a single result at the given 1-based rank."""
    return 1.0 / (k + rank)


def _fuse_ranked_lists(
    kw_ids: list[str],
    sem_ids: list[str],
    top_n: int,
) -> list[tuple[str, float, str]]:
    """
    Fuse two ranked ID lists using RRF.

    Args:
        kw_ids:  IDs in keyword rank order (best first)
        sem_ids: IDs in semantic rank order (best first)
        top_n:   Return only the top N fused results

    Returns:
        List of (id, rrf_score, rank_source) sorted by rrf_score descending.
    """
    scores: dict[str, float] = {}

    for rank, rid in enumerate(kw_ids, start=1):
        scores[rid] = scores.get(rid, 0.0) + _rrf_score(rank)

    for rank, rid in enumerate(sem_ids, start=1):
        scores[rid] = scores.get(rid, 0.0) + _rrf_score(rank)

    # Determine source attribution
    kw_set  = set(kw_ids)
    sem_set = set(sem_ids)

    fused = []
    for rid, score in sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_n]:
        if rid in kw_set and rid in sem_set:
            source = "both"
        elif rid in kw_set:
            source = "keyword"
        else:
            source = "semantic"
        fused.append((rid, round(score, 6), source))

    return fused


# ---------------------------------------------------------------------------
# Per-entity hybrid search
# ---------------------------------------------------------------------------

def _hybrid_packages(
    query: str,
    db_path: str,
    chroma_path: str,
    n: int,
) -> list[HybridPackageResult]:
    """Hybrid search over packages."""
    # Fetch more than n from each source so fusion has enough candidates
    fetch = min(n * 3, 50)

    kw_results  = kw_packages(query, db_path=db_path, limit=fetch)
    sem_results = semantic_search_packages(query, chroma_path=chroma_path, n_results=fetch)

    # Build ID lists  (keyword uses hash_id, semantic uses hash_id from metadata)
    kw_ids  = [r.hash_id for r in kw_results]
    sem_ids = [r.hash_id for r in sem_results]

    fused = _fuse_ranked_lists(kw_ids, sem_ids, top_n=n)

    # Build lookup maps
    kw_map  = {r.hash_id: r for r in kw_results}
    sem_map = {r.hash_id: r for r in sem_results}

    results = []
    for hash_id, rrf_score, source in fused:
        # Prefer keyword result (has full SQLite data), fall back to semantic
        r = kw_map.get(hash_id) or sem_map.get(hash_id)
        if r is None:
            continue
        results.append(
            HybridPackageResult(
                package_id=getattr(r, "package_id", 0),
                hash_id=hash_id,
                title=r.title,
                sub_title=getattr(r, "sub_title", ""),
                duration_days=getattr(r, "duration_days", 0),
                category=getattr(r, "category", ""),
                types=getattr(r, "types", []),
                destinations=getattr(r, "destinations", []),
                is_popular=bool(getattr(r, "is_popular", False)),
                permalink=getattr(r, "permalink", ""),
                short_description=getattr(r, "short_description", ""),
                rrf_score=rrf_score,
                rank_source=source,
            )
        )
    return results


def _hybrid_hotels(
    query: str,
    db_path: str,
    chroma_path: str,
    n: int,
) -> list[HybridHotelResult]:
    """Hybrid search over hotels."""
    fetch = min(n * 3, 50)

    kw_results  = kw_hotels(query, db_path=db_path, limit=fetch)
    sem_results = semantic_search_hotels(query, chroma_path=chroma_path, n_results=fetch)

    kw_ids  = [r.hotel_id for r in kw_results]
    sem_ids = [r.hotel_id for r in sem_results]

    fused = _fuse_ranked_lists(kw_ids, sem_ids, top_n=n)

    kw_map  = {r.hotel_id: r for r in kw_results}
    sem_map = {r.hotel_id: r for r in sem_results}

    results = []
    for hotel_id, rrf_score, source in fused:
        r = kw_map.get(hotel_id) or sem_map.get(hotel_id)
        if r is None:
            continue
        results.append(
            HybridHotelResult(
                hotel_id=hotel_id,
                name=r.name,
                city=r.city,
                region=r.region,
                rating=r.rating,
                facilities=getattr(r, "facilities", []),
                permalink=getattr(r, "permalink", ""),
                short_description=getattr(r, "short_description", ""),
                rrf_score=rrf_score,
                rank_source=source,
            )
        )
    return results


def _hybrid_itineraries(
    query: str,
    db_path: str,
    chroma_path: str,
    n: int,
) -> list[HybridItineraryResult]:
    """Hybrid search over itineraries."""
    fetch = min(n * 3, 50)

    kw_results  = kw_itineraries(query, db_path=db_path, limit=fetch)
    sem_results = semantic_search_itineraries(query, chroma_path=chroma_path, n_results=fetch)

    kw_ids  = [r.itinerary_id for r in kw_results]
    sem_ids = [r.itinerary_id for r in sem_results]

    fused = _fuse_ranked_lists(kw_ids, sem_ids, top_n=n)

    kw_map  = {r.itinerary_id: r for r in kw_results}
    sem_map = {r.itinerary_id: r for r in sem_results}

    results = []
    for itin_id, rrf_score, source in fused:
        r = kw_map.get(itin_id) or sem_map.get(itin_id)
        if r is None:
            continue
        results.append(
            HybridItineraryResult(
                itinerary_id=itin_id,
                package_hash_id=getattr(r, "package_hash_id", ""),
                package_title=getattr(r, "package_title", ""),
                day=getattr(r, "day", 0),
                title=r.title,
                details_snippet=getattr(r, "details", getattr(r, "details_snippet", ""))[:300],
                rrf_score=rrf_score,
                rank_source=source,
            )
        )
    return results


def _hybrid_visa(
    query: str,
    db_path: str,
    chroma_path: str,
    n: int,
) -> list[HybridVisaResult]:
    """Hybrid search over visa records."""
    fetch = min(n * 3, 50)

    kw_results  = kw_visa(query, db_path=db_path, limit=fetch)
    sem_results = semantic_search_visa(query, chroma_path=chroma_path, n_results=fetch)

    kw_ids  = [r.visa_id for r in kw_results]
    sem_ids = [r.visa_id for r in sem_results]

    fused = _fuse_ranked_lists(kw_ids, sem_ids, top_n=n)

    kw_map  = {r.visa_id: r for r in kw_results}
    sem_map = {r.visa_id: r for r in sem_results}

    results = []
    for visa_id, rrf_score, source in fused:
        r = kw_map.get(visa_id) or sem_map.get(visa_id)
        if r is None:
            continue
        results.append(
            HybridVisaResult(
                visa_id=visa_id,
                country=r.country,
                requirements_snippet=getattr(r, "requirements", getattr(r, "requirements_snippet", ""))[:400],
                rrf_score=rrf_score,
                rank_source=source,
            )
        )
    return results


# ---------------------------------------------------------------------------
# Unified hybrid search
# ---------------------------------------------------------------------------

def hybrid_search_all(
    query: str,
    db_path: str = DEFAULT_DB_PATH,
    chroma_path: str = DEFAULT_CHROMA_PATH,
    n: int = 10,
    include_types: set[str] | None = None,
) -> HybridResults:
    """
    Run hybrid search across all entity types.

    Combines FTS5 keyword (BM25) + ChromaDB semantic (cosine) results
    using Reciprocal Rank Fusion (RRF, k=60).

    Args:
        query:         Natural language search query
        db_path:       Path to SQLite database
        chroma_path:   Path to ChromaDB storage
        n:             Max results per entity type
        include_types: Limit to specific types. None = all.

    Returns:
        HybridResults with per-type lists sorted by RRF score descending.
    """
    if include_types is None:
        include_types = {"packages", "hotels", "itineraries", "visa"}

    out = HybridResults(query=query)

    if "packages" in include_types:
        out.packages = _hybrid_packages(query, db_path, chroma_path, n)

    if "hotels" in include_types:
        out.hotels = _hybrid_hotels(query, db_path, chroma_path, n)

    if "itineraries" in include_types:
        out.itineraries = _hybrid_itineraries(query, db_path, chroma_path, n)

    if "visa" in include_types:
        out.visa = _hybrid_visa(query, db_path, chroma_path, n)

    out.total = (
        len(out.packages) + len(out.hotels)
        + len(out.itineraries) + len(out.visa)
    )
    logger.info(
        "Hybrid search %r -> %d total (pkg=%d htl=%d itin=%d visa=%d)",
        query, out.total,
        len(out.packages), len(out.hotels),
        len(out.itineraries), len(out.visa),
    )
    return out
