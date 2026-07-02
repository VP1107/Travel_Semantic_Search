"""
api/routes/hotels.py
--------------------
Hotel listing and detail endpoints.

GET /hotels              -> paginated list
GET /hotels/{hotel_id}   -> full hotel detail
"""

import logging
import sqlite3
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from api.models import HotelDetail, HotelListResponse, HotelSummary

logger = logging.getLogger("api.hotels")
router = APIRouter(prefix="/hotels", tags=["Hotels"])

DEFAULT_DB = "db/travel.db"


def _get_conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _split_pipe(value: str | None) -> list[str]:
    if not value:
        return []
    return [v.strip() for v in value.split("|") if v.strip()]


@router.get(
    "",
    response_model=HotelListResponse,
    summary="List hotels",
    description="Returns a paginated list of hotels with optional city/region filters.",
)
def list_hotels(
    city: Annotated[str | None, Query(description="Filter by city")] = None,
    region: Annotated[str | None, Query(description="Filter by region keyword")] = None,
    rating: Annotated[str | None, Query(description="Filter by rating label")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: str = DEFAULT_DB,
) -> HotelListResponse:
    conn = _get_conn(db)
    try:
        conditions = ["status = 1"]
        params: list = []

        if city:
            conditions.append("LOWER(city) LIKE LOWER(?)")
            params.append(f"%{city}%")

        if region:
            conditions.append("LOWER(region) LIKE LOWER(?)")
            params.append(f"%{region}%")

        if rating:
            conditions.append("LOWER(rating) LIKE LOWER(?)")
            params.append(f"%{rating}%")

        where = " AND ".join(conditions)

        count_row = conn.execute(
            f"SELECT COUNT(*) as n FROM hotels WHERE {where}", params
        ).fetchone()
        total = count_row["n"]

        rows = conn.execute(
            f"""
            SELECT hotel_id, name, city, region, rating,
                   short_description, facilities, permalink
            FROM hotels
            WHERE {where}
            ORDER BY name ASC
            LIMIT ? OFFSET ?
            """,
            params + [limit, offset],
        ).fetchall()

        items = [
            HotelSummary(
                hotel_id=r["hotel_id"],
                name=r["name"],
                city=r["city"] or "",
                region=r["region"] or "",
                rating=r["rating"] or "",
                short_description=r["short_description"] or "",
                facilities=_split_pipe(r["facilities"]),
                permalink=r["permalink"] or "",
            )
            for r in rows
        ]
        return HotelListResponse(total=total, items=items)
    finally:
        conn.close()


@router.get(
    "/{hotel_id}",
    response_model=HotelDetail,
    summary="Get hotel detail",
    description="Returns full hotel detail including description and facilities.",
)
def get_hotel(hotel_id: str, db: str = DEFAULT_DB) -> HotelDetail:
    conn = _get_conn(db)
    try:
        row = conn.execute(
            """
            SELECT hotel_id, name, city, address, region, rating,
                   short_description, description, facilities, permalink
            FROM hotels
            WHERE hotel_id = ? AND status = 1
            """,
            (hotel_id,),
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail=f"Hotel {hotel_id!r} not found")

        return HotelDetail(
            hotel_id=row["hotel_id"],
            name=row["name"],
            city=row["city"] or "",
            address=row["address"] or "",
            region=row["region"] or "",
            rating=row["rating"] or "",
            short_description=row["short_description"] or "",
            description=row["description"] or "",
            facilities=_split_pipe(row["facilities"]),
            permalink=row["permalink"] or "",
        )
    finally:
        conn.close()
