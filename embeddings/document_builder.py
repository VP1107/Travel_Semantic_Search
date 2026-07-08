"""
embeddings/document_builder.py
-------------------------------
Builds rich text documents for each entity type before embedding.

The quality of semantic search depends entirely on what text
is embedded. Each builder produces a structured, information-dense
string that represents the entity's searchable content.

Why character limits?
    all-MiniLM-L6-v2 silently truncates at 256 tokens (~400-600 chars).
    We front-load the most important fields and truncate descriptions
    at the end, so title/category/destination data is never lost.

Public API:
    build_package_doc(pkg: dict)   -> str
    build_hotel_doc(hotel: dict)   -> str
    build_itinerary_doc(itin: dict)-> str
    build_visa_doc(visa: dict)     -> str
    build_document(entity_type, record) -> str   (dispatcher)
"""

from __future__ import annotations

# Character budget for long-form description fields
# The model truncates at ~256 tokens ≈ 512-600 chars for English text
_DESC_MAX = 500
_REQ_MAX = 700


def _trunc(text: str | None, max_len: int) -> str:
    """Return text truncated to max_len characters, or empty string."""
    if not text:
        return ""
    return text[:max_len]


def _join(items: list[str], sep: str = ", ") -> str:
    """Join a list of strings, returning empty string for empty list."""
    return sep.join(i for i in items if i)


# ---------------------------------------------------------------------------
# Per-entity builders
# ---------------------------------------------------------------------------

def build_package_doc(pkg: dict) -> str:
    """
    Build a search document for a travel package.

    Field priority (most → least important for search):
      1. title + sub_title       — core identity
      2. destinations            — geography (highest search intent)
      3. category + types        — trip style / traveller type
      4. short_description       — quick summary
      5. description (truncated) — rich detail
    """
    parts: list[str] = []

    title = pkg.get("title", "")
    sub_title = pkg.get("sub_title", "")
    if title:
        heading = f"{title}"
        if sub_title:
            heading += f". {sub_title}"
        parts.append(heading)

    destinations = _join(pkg.get("destinations", []), " | ")
    if destinations:
        parts.append(f"Destinations: {destinations}")

    category = pkg.get("category", "")
    types = _join(pkg.get("types", []))
    if category:
        parts.append(f"Category: {category}")
    if types:
        parts.append(f"Type: {types}")

    duration = pkg.get("duration_days", 0)
    if duration:
        parts.append(f"Duration: {duration} days")

    short_desc = pkg.get("short_description", "")
    if short_desc:
        parts.append(short_desc)

    description = _trunc(pkg.get("description", ""), _DESC_MAX)
    if description:
        parts.append(description)

    return "\n".join(parts)


def build_hotel_doc(hotel: dict) -> str:
    """
    Build a search document for a hotel.

    Field priority:
      1. name + city             — identity
      2. region                  — geography hierarchy
      3. rating + facilities     — key attributes
      4. short_description       — highlight summary
      5. description (truncated) — detailed copy
    """
    parts: list[str] = []

    name = hotel.get("name", "")
    city = hotel.get("city", "")
    if name:
        heading = name
        if city:
            heading += f". {city}"
        parts.append(heading)

    region = hotel.get("region", "")
    if region:
        parts.append(f"Region: {region}")

    rating = hotel.get("rating", "")
    if rating:
        parts.append(f"Rating: {rating}")

    facilities = _join(hotel.get("facilities", []))
    if facilities:
        parts.append(f"Facilities: {facilities}")

    short_desc = hotel.get("short_description", "")
    if short_desc:
        parts.append(short_desc)

    description = _trunc(hotel.get("description", ""), _DESC_MAX)
    if description:
        parts.append(description)

    return "\n".join(parts)


def build_itinerary_doc(itin: dict) -> str:
    """
    Build a search document for a single itinerary day.

    Field priority:
      1. package_title — which package this belongs to
      2. day + title   — what happens this day
      3. details       — full activity description
    """
    parts: list[str] = []

    package_title = itin.get("package_title", "")
    day = itin.get("day", "")
    title = itin.get("title", "")

    if package_title:
        parts.append(f"Package: {package_title}")

    if day and title:
        parts.append(f"Day {day}: {title}")
    elif title:
        parts.append(title)

    details = itin.get("details", "")
    if details:
        parts.append(details)

    return "\n".join(parts)


def build_visa_doc(visa: dict) -> str:
    """
    Build a search document for a visa record.

    Field priority:
      1. country name          — primary identifier
      2. requirements (trunc)  — documents, process, restrictions
    """
    parts: list[str] = []

    country = visa.get("country", "")
    if country:
        parts.append(f"Visa requirements for {country}")

    requirements = _trunc(visa.get("requirements", ""), _REQ_MAX)
    if requirements:
        parts.append(requirements)

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_BUILDERS = {
    "package": build_package_doc,
    "hotel": build_hotel_doc,
    "itinerary": build_itinerary_doc,
    "visa": build_visa_doc,
}


def build_document(entity_type: str, record: dict) -> str:
    """
    Dispatch to the correct builder by entity_type.

    Args:
        entity_type: one of "package", "hotel", "itinerary", "visa"
        record:      the entity dict from processed JSON

    Raises:
        ValueError: if entity_type is unrecognised
    """
    builder = _BUILDERS.get(entity_type)
    if builder is None:
        raise ValueError(
            f"Unknown entity type: {entity_type!r}. "
            f"Valid types: {list(_BUILDERS)}"
        )
    return builder(record)
