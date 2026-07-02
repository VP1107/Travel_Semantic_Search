"""
api/routes/hybrid.py
--------------------
Hybrid search endpoint — fuses keyword (FTS5) + semantic (ChromaDB)
results using Reciprocal Rank Fusion (RRF).

GET /search/hybrid?q=...&n=10&types=packages,hotels,itineraries,visa

Best of both worlds:
  - "Kerala"            → keyword wins (exact match)
  - "romantic sunset"   → semantic wins
  - "Goa honeymoon"     → both contribute → best ranking
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from search.hybrid_search import hybrid_search_all

logger = logging.getLogger("api.hybrid")

router = APIRouter(prefix="/search", tags=["Hybrid Search"])

_ALL_TYPES = {"packages", "hotels", "itineraries", "visa"}


# ---------------------------------------------------------------------------
# Response models (inline — mirrors semantic shape + rank_source)
# ---------------------------------------------------------------------------

class HybridPackageResult(BaseModel):
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
    rank_source: str
    result_type: str = "package"
    search_type: str = "hybrid"


class HybridHotelResult(BaseModel):
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


class HybridItineraryResult(BaseModel):
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


class HybridVisaResult(BaseModel):
    visa_id: str
    country: str
    requirements_snippet: str
    rrf_score: float
    rank_source: str
    result_type: str = "visa"
    search_type: str = "hybrid"


class HybridSearchResponse(BaseModel):
    query: str
    total: int
    search_type: str = "hybrid"
    rrf_note: str = (
        "rrf_score: higher = more relevant. "
        "rank_source: 'keyword'|'semantic'|'both'"
    )
    packages: list[HybridPackageResult] = Field(default_factory=list)
    hotels: list[HybridHotelResult] = Field(default_factory=list)
    itineraries: list[HybridItineraryResult] = Field(default_factory=list)
    visa: list[HybridVisaResult] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

def _parse_types(types_str: str | None) -> set[str]:
    if not types_str:
        return _ALL_TYPES
    requested = {t.strip().lower() for t in types_str.split(",") if t.strip()}
    valid = requested & _ALL_TYPES
    return valid or _ALL_TYPES


@router.get(
    "/hybrid",
    response_model=HybridSearchResponse,
    summary="Hybrid search — keyword + semantic via RRF",
    description=(
        "Combines FTS5 keyword (BM25) and ChromaDB semantic (cosine) results "
        "using **Reciprocal Rank Fusion (RRF)**.\n\n"
        "- Exact keyword matches are surfaced by BM25\n"
        "- Intent/meaning matches are surfaced by semantic\n"
        "- `rank_source` shows which signal(s) contributed to each result\n\n"
        "Use this as the **default search mode** for best overall relevance."
    ),
)
def hybrid_search(
    q: Annotated[str, Query(min_length=2, max_length=500,
                            description="Natural language or keyword query")],
    n: Annotated[int, Query(ge=1, le=50,
                            description="Max results per type (default 10)")] = 10,
    types: Annotated[str | None, Query(
        description="Comma-separated types: packages,hotels,itineraries,visa"
    )] = None,
) -> HybridSearchResponse:
    logger.info("Hybrid search: %r  n=%d  types=%s", q, n, types)

    try:
        raw = hybrid_search_all(
            query=q,
            n=n,
            include_types=_parse_types(types),
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.exception("Hybrid search error: %s", exc)
        raise HTTPException(status_code=500, detail="Hybrid search failed.")

    return HybridSearchResponse(
        query=raw.query,
        total=raw.total,
        packages=[HybridPackageResult(**vars(p)) for p in raw.packages],
        hotels=[HybridHotelResult(**vars(h)) for h in raw.hotels],
        itineraries=[HybridItineraryResult(**vars(i)) for i in raw.itineraries],
        visa=[HybridVisaResult(**vars(v)) for v in raw.visa],
    )
