"""
api/routes/packages.py
----------------------
Package listing and detail endpoints.

GET /packages                  -> paginated list
GET /packages/{package_id}     -> full detail with itineraries + hotels
"""

import logging
import sqlite3
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from api.models import (
    HotelSummary,
    ItinerarySummary,
    PackageDetail,
    PackageListResponse,
    PackageSummary,
)

logger = logging.getLogger("api.packages")
router = APIRouter(prefix="/packages", tags=["Packages"])

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
    response_model=PackageListResponse,
    summary="List all packages",
    description="Returns a paginated list of active travel packages, "
                "with optional filters for category and destination.",
)
def list_packages(
    category: Annotated[str | None, Query(description="Filter by category name")] = None,
    destination: Annotated[str | None, Query(description="Filter by destination keyword")] = None,
    popular: Annotated[bool | None, Query(description="Filter popular packages only")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: str = DEFAULT_DB,
) -> PackageListResponse:
    conn = _get_conn(db)
    try:
        conditions = ["status = 1"]
        params: list = []

        if category:
            conditions.append("LOWER(category) LIKE LOWER(?)")
            params.append(f"%{category}%")

        if destination:
            conditions.append("LOWER(destinations) LIKE LOWER(?)")
            params.append(f"%{destination}%")

        if popular is True:
            conditions.append("is_popular = 1")

        where = " AND ".join(conditions)

        # Count
        count_row = conn.execute(
            f"SELECT COUNT(*) as n FROM packages WHERE {where}", params
        ).fetchone()
        total = count_row["n"]

        # Fetch page
        rows = conn.execute(
            f"""
            SELECT package_id, hash_id, title, sub_title, duration_days,
                   short_description, category, types, destinations,
                   is_popular, permalink
            FROM packages
            WHERE {where}
            ORDER BY is_popular DESC, package_id ASC
            LIMIT ? OFFSET ?
            """,
            params + [limit, offset],
        ).fetchall()

        items = [
            PackageSummary(
                package_id=r["package_id"],
                hash_id=r["hash_id"],
                title=r["title"],
                sub_title=r["sub_title"] or "",
                duration_days=r["duration_days"] or 0,
                short_description=r["short_description"] or "",
                category=r["category"] or "",
                types=_split_pipe(r["types"]),
                destinations=_split_pipe(r["destinations"]),
                is_popular=bool(r["is_popular"]),
                permalink=r["permalink"] or "",
            )
            for r in rows
        ]
        return PackageListResponse(total=total, items=items)
    finally:
        conn.close()


@router.get(
    "/{package_id}",
    response_model=PackageDetail,
    summary="Get package detail",
    description="Returns full package detail including day-by-day itinerary and linked hotels.",
)
def get_package(package_id: int, db: str = DEFAULT_DB) -> PackageDetail:
    conn = _get_conn(db)
    try:
        # ── Package ──────────────────────────────────────────────────────
        row = conn.execute(
            """
            SELECT package_id, hash_id, title, sub_title, duration_days,
                   short_description, description, category, types,
                   destinations, is_popular, permalink
            FROM packages
            WHERE package_id = ? AND status = 1
            """,
            (package_id,),
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail=f"Package {package_id} not found")

        hash_id = row["hash_id"]

        # ── Itineraries ──────────────────────────────────────────────────
        itin_rows = conn.execute(
            """
            SELECT itinerary_id, day, title, details
            FROM itineraries
            WHERE package_hash_id = ?
            ORDER BY day ASC
            """,
            (hash_id,),
        ).fetchall()

        itineraries = [
            ItinerarySummary(
                itinerary_id=i["itinerary_id"],
                day=i["day"] or 0,
                title=i["title"] or "",
                details=i["details"] or "",
            )
            for i in itin_rows
        ]

        # ── Linked hotels ────────────────────────────────────────────────
        hotel_rows = conn.execute(
            """
            SELECT h.hotel_id, h.name, h.city, h.region, h.rating,
                   h.short_description, h.facilities, h.permalink
            FROM package_hotel_items phi
            JOIN hotels h ON phi.hotel_id = h.hotel_id
            WHERE phi.package_hash_id = ?
            ORDER BY phi.sort_order ASC, h.name ASC
            """,
            (hash_id,),
        ).fetchall()

        hotels: list[HotelSummary] = []
        for h in hotel_rows:
            hotels.append(
                HotelSummary(
                    hotel_id=h["hotel_id"],
                    name=h["name"],
                    city=h["city"] or "",
                    region=h["region"] or "",
                    rating=h["rating"] or "",
                    short_description=h["short_description"] or "",
                    facilities=_split_pipe(h["facilities"]),
                    permalink=h["permalink"] or "",
                )
            )

        return PackageDetail(
            package_id=row["package_id"],
            hash_id=row["hash_id"],
            title=row["title"],
            sub_title=row["sub_title"] or "",
            duration_days=row["duration_days"] or 0,
            short_description=row["short_description"] or "",
            description=row["description"] or "",
            category=row["category"] or "",
            types=_split_pipe(row["types"]),
            destinations=_split_pipe(row["destinations"]),
            is_popular=bool(row["is_popular"]),
            permalink=row["permalink"] or "",
            itineraries=itineraries,
            hotels=hotels,
        )
    finally:
        conn.close()
