"""
ingest/chroma_ingest.py
-----------------------
Populates ChromaDB with embeddings from the processed JSON files.

Collections:
    packages      — 150 records
    hotels        — 1,010 records
    itineraries   — 1,108 records
    visa          — 90 records

Each record stores:
    id:        stable string ID (e.g. "pkg_1", "htl_51e3c...")
    embedding: 384-dim float vector from all-MiniLM-L6-v2
    document:  the text that was embedded (for inspection / snippet)
    metadata:  key fields for display without SQLite round-trip

The collections are always deleted and recreated on each run
so ingest is fully idempotent.

Public API:
    ingest_all(processed_dir, chroma_path, embedder, batch_size) -> IngestStats
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

import chromadb

from embeddings.document_builder import (
    build_hotel_doc,
    build_itinerary_doc,
    build_package_doc,
    build_visa_doc,
)
from embeddings.embedder import Embedder

logger = logging.getLogger("ingest.chroma")

# Collection names — must match what semantic_search.py uses
COLLECTION_PACKAGES    = "packages"
COLLECTION_HOTELS      = "hotels"
COLLECTION_ITINERARIES = "itineraries"
COLLECTION_VISA        = "visa"

DEFAULT_BATCH_SIZE = 64


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class IngestStats:
    packages: int = 0
    hotels: int = 0
    itineraries: int = 0
    visa: int = 0
    elapsed_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.packages + self.hotels + self.itineraries + self.visa


# ---------------------------------------------------------------------------
# ChromaDB client factory
# ---------------------------------------------------------------------------

def get_chroma_client(chroma_path: str) -> chromadb.PersistentClient:
    """
    Return a persistent ChromaDB client at *chroma_path*.
    Creates the directory if it does not exist.
    """
    os.makedirs(chroma_path, exist_ok=True)
    return chromadb.PersistentClient(path=chroma_path)


def _reset_collection(
    client: chromadb.PersistentClient, name: str
) -> chromadb.Collection:
    """Delete collection if it exists, then create fresh."""
    try:
        client.delete_collection(name)
        logger.debug("Deleted existing collection: %s", name)
    except Exception:
        pass  # Collection didn't exist — fine
    return client.create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},   # cosine similarity
    )


# ---------------------------------------------------------------------------
# Per-entity ingest helpers
# ---------------------------------------------------------------------------

def _batch_add(
    collection: chromadb.Collection,
    ids: list[str],
    documents: list[str],
    embeddings: list[list[float]],
    metadatas: list[dict[str, Any]],
) -> None:
    """Add a batch to collection — ChromaDB requires all lists same length."""
    collection.add(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )


def _ingest_entity(
    *,
    collection: chromadb.Collection,
    records: list[dict],
    id_fn,           # record -> str ID
    doc_fn,          # record -> str document
    meta_fn,         # record -> dict metadata
    embedder: Embedder,
    batch_size: int,
    label: str,
) -> int:
    """
    Generic ingest loop for any entity type.

    Returns number of records successfully ingested.
    """
    total = len(records)
    ingested = 0
    logger.info("Ingesting %d %s records ...", total, label)

    for start in range(0, total, batch_size):
        batch = records[start : start + batch_size]
        batch_ids = [id_fn(r) for r in batch]
        batch_docs = [doc_fn(r) for r in batch]
        batch_meta = [meta_fn(r) for r in batch]

        # Encode the batch
        batch_embeddings = embedder.encode(batch_docs, batch_size=batch_size)

        _batch_add(
            collection,
            ids=batch_ids,
            documents=batch_docs,
            embeddings=batch_embeddings,
            metadatas=batch_meta,
        )

        ingested += len(batch)
        pct = ingested / total * 100
        logger.info("  %s  %d/%d  (%.0f%%)", label, ingested, total, pct)

    return ingested


# ---------------------------------------------------------------------------
# Metadata builders — what's stored alongside each embedding
# ---------------------------------------------------------------------------

def _pkg_meta(p: dict) -> dict[str, Any]:
    return {
        "package_id":   int(p.get("package_id") or 0),
        "hash_id":      str(p.get("hash_id", "")),
        "title":        str(p.get("title", "")),
        "sub_title":    str(p.get("sub_title", "")),
        "duration_days": int(p.get("duration_days") or 0),
        "category":     str(p.get("category", "")),
        "types":        "|".join(p.get("types", [])),
        "destinations": "|".join(p.get("destinations", [])),
        "is_popular":   int(bool(p.get("is_popular", False))),
        "permalink":    str(p.get("permalink", "")),
        "short_description": str(p.get("short_description", ""))[:300],
    }


def _hotel_meta(h: dict) -> dict[str, Any]:
    return {
        "hotel_id":     str(h.get("hotel_id", "")),
        "name":         str(h.get("name", "")),
        "city":         str(h.get("city", "")),
        "region":       str(h.get("region", "")),
        "rating":       str(h.get("rating", "")),
        "facilities":   "|".join(h.get("facilities", []))[:200],
        "permalink":    str(h.get("permalink", "")),
        "short_description": str(h.get("short_description", ""))[:300],
    }


def _itin_meta(i: dict) -> dict[str, Any]:
    return {
        "itinerary_id":  str(i.get("itinerary_id", "")),
        "package_hash_id": str(i.get("package_hash_id", "")),
        "package_title": str(i.get("package_title", "")),
        "day":           int(i.get("day") or 0),
        "title":         str(i.get("title", "")),
        "details_snippet": str(i.get("details", ""))[:300],
    }


def _visa_meta(v: dict) -> dict[str, Any]:
    return {
        "visa_id":      str(v.get("visa_id", "")),
        "country":      str(v.get("country", "")),
        "requirements_snippet": str(v.get("requirements", ""))[:400],
    }


# ---------------------------------------------------------------------------
# Main ingest function
# ---------------------------------------------------------------------------

def ingest_all(
    processed_dir: str,
    chroma_path: str,
    embedder: Embedder,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> IngestStats:
    """
    Load all processed JSON files and populate ChromaDB collections.

    Args:
        processed_dir: directory containing packages.json, hotels.json, etc.
        chroma_path:   path for persistent ChromaDB storage
        embedder:      loaded Embedder instance
        batch_size:    number of records per embedding batch

    Returns:
        IngestStats with counts and timing.
    """
    stats = IngestStats()
    t0 = time.time()

    client = get_chroma_client(chroma_path)

    # ── Load processed JSON files ────────────────────────────────────────
    def _load(filename: str) -> list[dict]:
        path = os.path.join(processed_dir, filename)
        if not os.path.exists(path):
            logger.warning("File not found — skipping: %s", path)
            return []
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    packages    = _load("packages.json")
    hotels      = _load("hotels.json")
    itineraries = _load("itineraries.json")
    visa        = _load("visa.json")

    # ── Packages ─────────────────────────────────────────────────────────
    col_pkg = _reset_collection(client, COLLECTION_PACKAGES)
    stats.packages = _ingest_entity(
        collection=col_pkg,
        records=packages,
        id_fn=lambda p: f"pkg_{p['package_id']}",
        doc_fn=build_package_doc,
        meta_fn=_pkg_meta,
        embedder=embedder,
        batch_size=batch_size,
        label="packages",
    )

    # ── Hotels ───────────────────────────────────────────────────────────
    col_htl = _reset_collection(client, COLLECTION_HOTELS)
    stats.hotels = _ingest_entity(
        collection=col_htl,
        records=hotels,
        id_fn=lambda h: f"htl_{h['hotel_id']}",
        doc_fn=build_hotel_doc,
        meta_fn=_hotel_meta,
        embedder=embedder,
        batch_size=batch_size,
        label="hotels",
    )

    # ── Itineraries ──────────────────────────────────────────────────────
    col_itin = _reset_collection(client, COLLECTION_ITINERARIES)
    stats.itineraries = _ingest_entity(
        collection=col_itin,
        records=itineraries,
        id_fn=lambda i: f"itn_{i['itinerary_id']}",
        doc_fn=build_itinerary_doc,
        meta_fn=_itin_meta,
        embedder=embedder,
        batch_size=batch_size,
        label="itineraries",
    )

    # ── Visa ─────────────────────────────────────────────────────────────
    col_visa = _reset_collection(client, COLLECTION_VISA)
    stats.visa = _ingest_entity(
        collection=col_visa,
        records=visa,
        id_fn=lambda v: f"vis_{v['visa_id']}",
        doc_fn=build_visa_doc,
        meta_fn=_visa_meta,
        embedder=embedder,
        batch_size=batch_size,
        label="visa",
    )

    stats.elapsed_seconds = time.time() - t0
    return stats
