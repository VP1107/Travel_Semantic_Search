"""
ai/context_builder.py
---------------------
Formats retrieved search results into a structured LLM prompt context block.

Rules (per GUIDELINES.md):
  - Retrieval MUST happen before context building
  - Sources must be trackable (IDs, titles, permalinks preserved)
  - Context must be concise to fit within LLM token windows

Public API:
    build_context(results, max_chars) -> ContextBlock
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from search.hybrid_search import HybridResults


# Max characters for the full context block sent to the LLM
# Gemini 1.5/2.0 flash supports 1M tokens, but we keep context focused
_MAX_CONTEXT_CHARS = 6000


@dataclass
class SourceRef:
    """Traceable source reference — always returned with the answer."""
    result_type: str       # "package", "hotel", "itinerary", "visa"
    title: str             # Display title
    permalink: str = ""
    entity_id: str = ""


@dataclass
class ContextBlock:
    """
    Structured context ready to be injected into the LLM prompt.

    Attributes:
        text:    Formatted context string for the LLM
        sources: Traceable list of source entities used
        count:   Number of source entities included
    """
    text: str
    sources: list[SourceRef] = field(default_factory=list)
    count: int = 0


def build_context(
    results: HybridResults,
    max_chars: int = _MAX_CONTEXT_CHARS,
) -> ContextBlock:
    """
    Convert hybrid search results into a formatted LLM context block.

    Packages and itineraries are prioritised (most travel-query-relevant).
    Hotels and visa follow. Each section is clearly labelled.

    Args:
        results:   HybridResults from hybrid_search_all()
        max_chars: Hard cap on total context characters

    Returns:
        ContextBlock with formatted text and source references.
    """
    sections: list[str] = []
    sources: list[SourceRef] = []
    total_chars = 0

    def _add(text: str) -> bool:
        nonlocal total_chars
        if total_chars + len(text) > max_chars:
            return False
        sections.append(text)
        total_chars += len(text)
        return True

    # ── Packages ─────────────────────────────────────────────────────────
    if results.packages:
        _add("\n### TRAVEL PACKAGES\n")
        for pkg in results.packages:
            dest = " | ".join(pkg.destinations[:3]) if pkg.destinations else "N/A"
            types = ", ".join(pkg.types[:4]) if pkg.types else ""
            block = (
                f"Package: {pkg.title}\n"
                f"  Duration: {pkg.duration_days} days | Category: {pkg.category}\n"
                f"  Types: {types}\n"
                f"  Destinations: {dest}\n"
                f"  Description: {pkg.short_description[:300]}\n"
                f"  [Source: package/{pkg.hash_id}]\n\n"
            )
            if not _add(block):
                break
            sources.append(SourceRef(
                result_type="package",
                title=pkg.title,
                permalink=pkg.permalink,
                entity_id=pkg.hash_id,
            ))

    # ── Itineraries ──────────────────────────────────────────────────────
    if results.itineraries:
        _add("\n### ITINERARY HIGHLIGHTS\n")
        for itin in results.itineraries[:6]:   # cap to avoid context bloat
            block = (
                f"Itinerary [{itin.package_title} – Day {itin.day}]: {itin.title}\n"
                f"  {itin.details_snippet[:250]}\n\n"
            )
            if not _add(block):
                break
            sources.append(SourceRef(
                result_type="itinerary",
                title=f"{itin.package_title} – Day {itin.day}: {itin.title}",
                entity_id=itin.itinerary_id,
            ))

    # ── Hotels ───────────────────────────────────────────────────────────
    if results.hotels:
        _add("\n### HOTELS\n")
        for hotel in results.hotels[:8]:
            fac = ", ".join(hotel.facilities[:5]) if hotel.facilities else "N/A"
            block = (
                f"Hotel: {hotel.name} — {hotel.city} ({hotel.rating})\n"
                f"  Region: {hotel.region}\n"
                f"  Facilities: {fac}\n"
                f"  {hotel.short_description[:200]}\n\n"
            )
            if not _add(block):
                break
            sources.append(SourceRef(
                result_type="hotel",
                title=f"{hotel.name}, {hotel.city}",
                permalink=hotel.permalink,
                entity_id=hotel.hotel_id,
            ))

    # ── Visa ─────────────────────────────────────────────────────────────
    if results.visa:
        _add("\n### VISA REQUIREMENTS\n")
        for vis in results.visa[:4]:
            block = (
                f"Country: {vis.country}\n"
                f"  {vis.requirements_snippet[:400]}\n\n"
            )
            if not _add(block):
                break
            sources.append(SourceRef(
                result_type="visa",
                title=f"Visa: {vis.country}",
                entity_id=vis.visa_id,
            ))

    context_text = "".join(sections).strip()
    return ContextBlock(
        text=context_text,
        sources=sources,
        count=len(sources),
    )
