"""
api/routes/semantic.py
----------------------
Semantic search endpoint powered by ChromaDB + all-MiniLM-L6-v2.

GET /search/semantic?q=romantic+beach+holiday&n=10&types=packages,hotels

Returns results grouped by entity type, ordered by cosine distance
(lower distance = more semantically similar to query).

Key difference from keyword search (/search):
  - Understands intent, not just exact words
  - "romantic getaway" matches honeymoon packages
  - "passport documents" matches visa requirements
  - "mountain monastery peace" matches Ladakh/Sikkim packages
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from api.models import (
    SemanticHotelResult,
    SemanticItineraryResult,
    SemanticPackageResult,
    SemanticSearchResponse,
    SemanticVisaResult,
)
from search.semantic_search import semantic_search_all

logger = logging.getLogger("api.semantic")

router = APIRouter(prefix="/search", tags=["Semantic Search"])

# Default entity types searched if none specified
_ALL_TYPES = {"packages", "hotels", "itineraries", "visa"}

_VALID_TYPES = _ALL_TYPES


def _parse_types(types_str: str | None) -> set[str]:
    """
    Parse a comma-separated types filter string.

    e.g. "packages,hotels" -> {"packages", "hotels"}
    Returns all types if input is None or empty.
    Silently ignores invalid type names.
    """
    if not types_str:
        return _ALL_TYPES
    requested = {t.strip().lower() for t in types_str.split(",") if t.strip()}
    valid = requested & _VALID_TYPES
    if not valid:
        return _ALL_TYPES
    return valid


@router.get(
    "/semantic",
    response_model=SemanticSearchResponse,
    summary="Semantic search using vector similarity",
    description=(
        "Search travel packages, hotels, itineraries, and visa records "
        "using meaning-based (semantic) matching powered by all-MiniLM-L6-v2 "
        "and ChromaDB.\n\n"
        "Unlike keyword search, this understands **intent** and **meaning**:\n"
        "- `'romantic beach sunset'` → finds Goa/Maldives honeymoon packages\n"
        "- `'mountain monastery spiritual retreat'` → finds Ladakh/Sikkim packages\n"
        "- `'passport requirements documents'` → finds visa information\n\n"
        "Results include a **distance** score (0.0 = perfect, ~1.0 = unrelated)."
    ),
)
def semantic_search(
    q: Annotated[
        str,
        Query(
            min_length=3,
            max_length=500,
            description="Natural language search query",
            examples=["romantic beach holiday for couples"],
        ),
    ],
    n: Annotated[
        int,
        Query(
            ge=1,
            le=50,
            description="Max results per entity type (default: 10)",
        ),
    ] = 10,
    types: Annotated[
        str | None,
        Query(
            description=(
                "Comma-separated entity types to search. "
                "Options: packages, hotels, itineraries, visa. "
                "Default: all types."
            ),
            examples=["packages,hotels"],
        ),
    ] = None,
    chroma: Annotated[
        str,
        Query(include_in_schema=False),
    ] = "db/chroma",
) -> SemanticSearchResponse:
    """
    Semantic search endpoint.

    The model is loaded lazily on first call — expect ~2-3 second delay
    on the very first request after server start. Subsequent requests
    use the cached singleton and are fast (~50-200ms).
    """
    logger.info("Semantic search: %r  n=%d  types=%s", q, n, types)

    include_types = _parse_types(types)

    try:
        raw = semantic_search_all(
            query=q,
            chroma_path=chroma,
            n_results=n,
            include_types=include_types,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                str(exc) + "\n\nRun 'python run_ingest.py' to build the vector store."
            ),
        )
    except Exception as exc:
        logger.exception("Semantic search error: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Semantic search failed. Check server logs.",
        )

    return SemanticSearchResponse(
        query=raw.query,
        total=raw.total,
        packages=[
            SemanticPackageResult(
                package_id=p.package_id,
                hash_id=p.hash_id,
                title=p.title,
                sub_title=p.sub_title,
                duration_days=p.duration_days,
                category=p.category,
                types=p.types,
                destinations=p.destinations,
                is_popular=p.is_popular,
                permalink=p.permalink,
                short_description=p.short_description,
                distance=p.distance,
            )
            for p in raw.packages
        ],
        hotels=[
            SemanticHotelResult(
                hotel_id=h.hotel_id,
                name=h.name,
                city=h.city,
                region=h.region,
                rating=h.rating,
                facilities=h.facilities,
                permalink=h.permalink,
                short_description=h.short_description,
                distance=h.distance,
            )
            for h in raw.hotels
        ],
        itineraries=[
            SemanticItineraryResult(
                itinerary_id=i.itinerary_id,
                package_hash_id=i.package_hash_id,
                package_title=i.package_title,
                day=i.day,
                title=i.title,
                details_snippet=i.details_snippet,
                distance=i.distance,
            )
            for i in raw.itineraries
        ],
        visa=[
            SemanticVisaResult(
                visa_id=v.visa_id,
                country=v.country,
                requirements_snippet=v.requirements_snippet,
                distance=v.distance,
            )
            for v in raw.visa
        ],
    )
