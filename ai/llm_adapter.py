"""
ai/llm_adapter.py
-----------------
Provider-agnostic LLM interface.

Currently supports: Google Gemini (gemini-2.0-flash)
Designed to add: OpenAI, Ollama — just add a new _Provider class.

Configuration (via environment variables):
    LLM_PROVIDER   = "gemini" (default)
    GEMINI_API_KEY = your API key

Public API:
    get_llm()           -> LLMAdapter (singleton)
    LLMAdapter.chat(messages) -> str
"""

from __future__ import annotations

import logging
import os
import threading
from abc import ABC, abstractmethod

logger = logging.getLogger("ai.llm")

_LOCK = threading.Lock()
_INSTANCE: LLMAdapter | None = None


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class LLMAdapter(ABC):
    """Provider-agnostic LLM interface."""

    @abstractmethod
    def generate(self, system_prompt: str, user_message: str) -> str:
        """
        Generate a response given a system prompt and user message.

        Args:
            system_prompt: Instruction context (includes retrieved travel data)
            user_message:  The traveller's question

        Returns:
            Generated text response (string).

        Raises:
            RuntimeError: If the API call fails after retries.
        """

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier string."""


# ---------------------------------------------------------------------------
# Gemini implementation
# ---------------------------------------------------------------------------

class GeminiAdapter(LLMAdapter):
    """
    Adapter for Google Gemini via the google-generativeai SDK.

    Model: gemini-2.0-flash (fast, cost-effective, strong reasoning)
    """

    _MODEL = "gemini-2.0-flash"

    def __init__(self, api_key: str) -> None:
        import google.generativeai as genai  # lazy import

        genai.configure(api_key=api_key)
        self._client = genai.GenerativeModel(
            model_name=self._MODEL,
            generation_config={
                "temperature": 0.3,       # low temp = factual, less hallucination
                "top_p": 0.9,
                "max_output_tokens": 1024,
            },
        )
        logger.info("Gemini adapter initialised: %s", self._MODEL)

    @property
    def model_name(self) -> str:
        return self._MODEL

    def generate(self, system_prompt: str, user_message: str) -> str:
        """Call Gemini with a combined system + user message."""
        try:
            # Gemini API: combine system prompt + user turn
            full_prompt = f"{system_prompt}\n\n---\n\nUser question: {user_message}"
            response = self._client.generate_content(full_prompt)
            return response.text.strip()
        except Exception as exc:
            logger.error("Gemini generation failed: %s", exc)
            raise RuntimeError(f"LLM generation failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def _build_adapter() -> LLMAdapter:
    provider = os.environ.get("LLM_PROVIDER", "gemini").lower()

    if provider == "gemini":
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            raise EnvironmentError(
                "GEMINI_API_KEY environment variable is not set.\n"
                "Add it to your .env file: GEMINI_API_KEY=your_key_here\n"
                "Get a free key at: https://aistudio.google.com/apikey"
            )
        return GeminiAdapter(api_key=api_key)

    raise ValueError(
        f"Unknown LLM_PROVIDER: {provider!r}. "
        "Supported: 'gemini'"
    )


def get_llm() -> LLMAdapter:
    """
    Return the process-level LLMAdapter singleton.
    Thread-safe. Raises EnvironmentError if API key is missing.
    """
    global _INSTANCE  # noqa: PLW0603
    if _INSTANCE is None:
        with _LOCK:
            if _INSTANCE is None:
                _INSTANCE = _build_adapter()
    return _INSTANCE
