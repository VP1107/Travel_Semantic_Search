"""
run_ingest.py
-------------
CLI entry point for the ChromaDB embedding ingest pipeline.

Run this AFTER run_etl.py (which produces data/processed/*.json).

Usage:
    python run_ingest.py

Environment variables (or .env):
    PROCESSED_DATA_DIR   Path to processed JSON files  (default: data/processed)
    CHROMA_DB_PATH       Path for ChromaDB storage     (default: db/chroma)
    LOG_FILE             Log file path                 (default: logs/etl.log)

What it does:
    1. Loads the Embedder (downloads all-MiniLM-L6-v2 on first run)
    2. Reads all processed JSON files
    3. Builds text documents per entity
    4. Batch-encodes with all-MiniLM-L6-v2 (384-dim vectors)
    5. Populates 4 ChromaDB collections (packages/hotels/itineraries/visa)
    6. Reports counts and timing
"""

import logging
import os
import sys
import time

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            os.environ.get("LOG_FILE", "logs/etl.log"),
            encoding="utf-8",
        ),
    ],
)

logger = logging.getLogger("ingest.runner")

from embeddings.embedder import get_embedder          # noqa: E402
from ingest.chroma_ingest import ingest_all           # noqa: E402


def main() -> int:
    processed_dir = os.environ.get("PROCESSED_DATA_DIR", "data/processed")
    chroma_path   = os.environ.get("CHROMA_DB_PATH",    "db/chroma")

    logger.info("=" * 60)
    logger.info("Travel Search — Embedding Ingest Pipeline")
    logger.info("=" * 60)
    logger.info("Processed data : %s", processed_dir)
    logger.info("ChromaDB path  : %s", chroma_path)
    logger.info("Model          : all-MiniLM-L6-v2")

    # Validate processed data exists
    required = ["packages.json", "hotels.json", "itineraries.json", "visa.json"]
    for fname in required:
        fpath = os.path.join(processed_dir, fname)
        if not os.path.exists(fpath):
            logger.error(
                "Missing processed file: %s\n"
                "Run 'python run_etl.py' first.",
                fpath,
            )
            return 1

    # ── Step 1: Load model ────────────────────────────────────────────────
    logger.info("-" * 40)
    logger.info("STEP 1/2  Loading embedding model ...")
    logger.info("(First run downloads ~90 MB from HuggingFace)")
    try:
        embedder = get_embedder()
    except Exception as exc:
        logger.error("Failed to load model: %s", exc)
        return 1

    # ── Step 2: Ingest all entities ───────────────────────────────────────
    logger.info("-" * 40)
    logger.info("STEP 2/2  Ingesting into ChromaDB ...")
    try:
        stats = ingest_all(
            processed_dir=processed_dir,
            chroma_path=chroma_path,
            embedder=embedder,
            batch_size=64,
        )
    except Exception as exc:
        logger.exception("Ingest failed: %s", exc)
        return 1

    # ── Summary ───────────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("Ingest complete in %.1fs", stats.elapsed_seconds)
    logger.info("  Packages    : %d", stats.packages)
    logger.info("  Hotels      : %d", stats.hotels)
    logger.info("  Itineraries : %d", stats.itineraries)
    logger.info("  Visa        : %d", stats.visa)
    logger.info("  Total       : %d vectors stored", stats.total)
    logger.info("  ChromaDB    : %s", chroma_path)
    logger.info("=" * 60)

    if stats.errors:
        logger.warning("Errors encountered: %d", len(stats.errors))
        for err in stats.errors:
            logger.warning("  %s", err)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
