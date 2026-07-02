"""
api/models.py
-------------
Pydantic response schemas for all API endpoints.

These are strictly output models — they define what the API returns.
Input validation is handled at the route level.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Package models
# ---------------------------------------------------------------------------

class PackageSummary(BaseModel):
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
    score: float | None = None
    result_type: str = "package"


class ItinerarySummary(BaseModel):
    itinerary_id: str
    day: int
    title: str
    details: str


class PackageDetail(PackageSummary):
    description: str
    itineraries: list[ItinerarySummary] = Field(default_factory=list)
    hotels: list["HotelSummary"] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Hotel models
# ---------------------------------------------------------------------------

class HotelSummary(BaseModel):
    hotel_id: str
    name: str
    city: str
    region: str
    rating: str
    short_description: str
    facilities: list[str]
    permalink: str
    score: float | None = None
    result_type: str = "hotel"


class HotelDetail(HotelSummary):
    description: str
    address: str


# ---------------------------------------------------------------------------
# Visa models
# ---------------------------------------------------------------------------

class VisaSummary(BaseModel):
    visa_id: str
    country: str
    requirements: str
    score: float | None = None
    result_type: str = "visa"


# ---------------------------------------------------------------------------
# Itinerary search result model
# ---------------------------------------------------------------------------

class ItineraryResult(BaseModel):
    itinerary_id: str
    package_title: str
    package_hash_id: str
    day: int
    title: str
    details: str
    score: float | None = None
    result_type: str = "itinerary"


# ---------------------------------------------------------------------------
# Unified search response
# ---------------------------------------------------------------------------

class SearchResponse(BaseModel):
    query: str
    total: int
    packages: list[PackageSummary] = Field(default_factory=list)
    hotels: list[HotelSummary] = Field(default_factory=list)
    visa: list[VisaSummary] = Field(default_factory=list)
    itineraries: list[ItineraryResult] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Generic list responses
# ---------------------------------------------------------------------------

class PackageListResponse(BaseModel):
    total: int
    items: list[PackageSummary]


class HotelListResponse(BaseModel):
    total: int
    items: list[HotelSummary]


class VisaListResponse(BaseModel):
    total: int
    items: list[VisaSummary]


# ---------------------------------------------------------------------------
# Error response
# ---------------------------------------------------------------------------

class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None


# ---------------------------------------------------------------------------
# Semantic search models  (Phase 2)
# ---------------------------------------------------------------------------

class SemanticPackageResult(BaseModel):
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


class SemanticHotelResult(BaseModel):
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


class SemanticItineraryResult(BaseModel):
    itinerary_id: str
    package_hash_id: str
    package_title: str
    day: int
    title: str
    details_snippet: str
    distance: float
    result_type: str = "itinerary"
    search_type: str = "semantic"


class SemanticVisaResult(BaseModel):
    visa_id: str
    country: str
    requirements_snippet: str
    distance: float
    result_type: str = "visa"
    search_type: str = "semantic"


class SemanticSearchResponse(BaseModel):
    query: str
    total: int
    search_type: str = "semantic"
    distance_note: str = (
        "distance: 0.0 = perfect match, ~0.5 = related, ~1.0 = unrelated"
    )
    packages: list[SemanticPackageResult] = Field(default_factory=list)
    hotels: list[SemanticHotelResult] = Field(default_factory=list)
    itineraries: list[SemanticItineraryResult] = Field(default_factory=list)
    visa: list[SemanticVisaResult] = Field(default_factory=list)
