"""
api/routes/search.py
--------------------
Unified search endpoint.

GET /search?q=Kerala+family+trip&limit=10
"""

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from api.models import SearchResponse, PackageSummary, HotelSummary, VisaSummary, ItineraryResult
from search.keyword_search import search_all

logger = logging.getLogger("api.search")
router = APIRouter(prefix="/search", tags=["Search"])


@router.get(
    "",
    response_model=SearchResponse,
    summary="Unified keyword search",
    description=(
        "Search across packages, hotels, visa records, and itineraries "
        "using BM25 full-text ranking. Results are grouped by entity type."
    ),
)
def search(
    q: Annotated[
        str,
        Query(
            min_length=2,
            max_length=200,
            description="Search query, e.g. 'Kerala family trip'",
        ),
    ],
    limit: Annotated[
        int,
        Query(ge=1, le=50, description="Max results per entity type"),
    ] = 10,
    db: Annotated[
        str,
        Query(include_in_schema=False),
    ] = "db/travel.db",
) -> SearchResponse:
    """
    Unified search across all travel data.

    Returns results grouped by type: packages, hotels, visa, itineraries.
    Each result includes a BM25 relevance score (lower = more relevant in FTS5).
    """
    logger.info("Search query: %r  limit=%d", q, limit)

    try:
        raw = search_all(query=q, db_path=db, limit=limit)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.exception("Search error: %s", exc)
        raise HTTPException(status_code=500, detail="Search failed. Check logs.")

    return SearchResponse(
        query=raw.query,
        total=raw.total,
        packages=[
            PackageSummary(
                package_id=p.package_id,
                hash_id=p.hash_id,
                title=p.title,
                sub_title=p.sub_title,
                duration_days=p.duration_days,
                short_description=p.short_description,
                category=p.category,
                types=p.types,
                destinations=p.destinations,
                is_popular=p.is_popular,
                permalink=p.permalink,
                score=p.score,
            )
            for p in raw.packages
        ],
        hotels=[
            HotelSummary(
                hotel_id=h.hotel_id,
                name=h.name,
                city=h.city,
                region=h.region,
                rating=h.rating,
                short_description=h.short_description,
                facilities=h.facilities,
                permalink=h.permalink,
                score=h.score,
            )
            for h in raw.hotels
        ],
        visa=[
            VisaSummary(
                visa_id=v.visa_id,
                country=v.country,
                requirements=v.requirements,
                score=v.score,
            )
            for v in raw.visa
        ],
        itineraries=[
            ItineraryResult(
                itinerary_id=i.itinerary_id,
                package_title=i.package_title,
                package_hash_id=i.package_hash_id,
                day=i.day,
                title=i.title,
                details=i.details,
                score=i.score,
            )
            for i in raw.itineraries
        ],
    )
