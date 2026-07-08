"""
embeddings/embedder.py
----------------------
Singleton wrapper around the SentenceTransformer model.

Loads all-MiniLM-L6-v2 once per process and reuses it for
all encode calls — avoids costly repeated model initialisation.

Public API:
    get_embedder()               -> Embedder (singleton)
    Embedder.encode(texts)       -> list[list[float]]
    Embedder.encode_one(text)    -> list[float]

Model spec:
    Name:       all-MiniLM-L6-v2
    Dimensions: 384
    Max tokens: 256  (longer text is silently truncated by the model)
    Similarity: cosine
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger("embeddings.embedder")

# ── Constants ────────────────────────────────────────────────────────────────
MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
_BATCH_SIZE_DEFAULT = 64          # safe default for CPU
_LOCK = threading.Lock()          # guard singleton init
_INSTANCE: Embedder | None = None # module-level singleton


# ── Embedder class ───────────────────────────────────────────────────────────

class Embedder:
    """
    Thin wrapper around SentenceTransformer that manages the singleton lifecycle.

    Do not instantiate directly — use get_embedder() instead.
    """

    def __init__(self, model_name: str = MODEL_NAME) -> None:
        logger.info("Loading embedding model: %s", model_name)
        t0 = time.time()

        # Lazy import — keeps startup fast when embeddings are not needed
        from sentence_transformers import SentenceTransformer  # noqa: PLC0415

        self._model: SentenceTransformer = SentenceTransformer(model_name)
        self.model_name = model_name
        self.dim = EMBEDDING_DIM

        elapsed = time.time() - t0
        logger.info("Model loaded in %.2fs (dim=%d)", elapsed, self.dim)

    # ── Encode ───────────────────────────────────────────────────────────────

    def encode(
        self,
        texts: list[str],
        batch_size: int = _BATCH_SIZE_DEFAULT,
        show_progress: bool = False,
    ) -> list[list[float]]:
        """
        Encode a list of texts into embedding vectors.

        Args:
            texts:         Texts to encode. Empty strings are safe.
            batch_size:    Number of texts per GPU/CPU batch.
            show_progress: Show tqdm progress bar (useful for large ingests).

        Returns:
            List of 384-dim float lists, one per input text.
        """
        if not texts:
            return []

        # Replace empty strings with a single space to avoid model errors
        safe_texts = [t if t.strip() else " " for t in texts]

        embeddings = self._model.encode(
            safe_texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            convert_to_numpy=True,
            normalize_embeddings=True,   # L2-normalise for cosine similarity
        )
        return embeddings.tolist()

    def encode_one(self, text: str) -> list[float]:
        """
        Encode a single string. Convenience wrapper around encode().
        """
        return self.encode([text])[0]


# ── Singleton accessor ────────────────────────────────────────────────────────

def get_embedder() -> Embedder:
    """
    Return the process-level Embedder singleton.

    Thread-safe: model is loaded at most once even under concurrent requests.
    """
    global _INSTANCE  # noqa: PLW0603
    if _INSTANCE is None:
        with _LOCK:
            if _INSTANCE is None:          # double-checked locking
                _INSTANCE = Embedder()
    return _INSTANCE
