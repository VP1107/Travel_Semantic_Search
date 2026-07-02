"""
api/routes/visa.py
------------------
Visa information endpoints.

GET /visa                    -> list all visa records
GET /visa/{country}          -> visa requirements for a specific country
"""

import logging
import sqlite3
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from api.models import VisaListResponse, VisaSummary

logger = logging.getLogger("api.visa")
router = APIRouter(prefix="/visa", tags=["Visa"])

DEFAULT_DB = "db/travel.db"


def _get_conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


@router.get(
    "",
    response_model=VisaListResponse,
    summary="List all visa records",
    description="Returns visa requirements for all supported countries.",
)
def list_visa(
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: str = DEFAULT_DB,
) -> VisaListResponse:
    conn = _get_conn(db)
    try:
        count_row = conn.execute(
            "SELECT COUNT(*) as n FROM visa WHERE status = 1"
        ).fetchone()
        total = count_row["n"]

        rows = conn.execute(
            """
            SELECT visa_id, country, requirements
            FROM visa
            WHERE status = 1
            ORDER BY country ASC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()

        items = [
            VisaSummary(
                visa_id=r["visa_id"],
                country=r["country"],
                requirements=r["requirements"] or "",
            )
            for r in rows
        ]
        return VisaListResponse(total=total, items=items)
    finally:
        conn.close()


@router.get(
    "/{country}",
    response_model=VisaSummary,
    summary="Get visa requirements by country",
    description="Returns full visa requirements for the specified country name. "
                "Case-insensitive exact match.",
)
def get_visa(country: str, db: str = DEFAULT_DB) -> VisaSummary:
    conn = _get_conn(db)
    try:
        row = conn.execute(
            """
            SELECT visa_id, country, requirements
            FROM visa
            WHERE LOWER(country) = LOWER(?) AND status = 1
            """,
            (country,),
        ).fetchone()

        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"No visa record found for country: {country!r}. "
                       "Try GET /visa to see available countries.",
            )

        return VisaSummary(
            visa_id=row["visa_id"],
            country=row["country"],
            requirements=row["requirements"] or "",
        )
    finally:
        conn.close()
