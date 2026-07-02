"""
ai/rag_chain.py
---------------
Orchestrates the full RAG pipeline:
    Retrieve → Build Context → Generate → Return Answer + Sources

Strict rule enforcement (per GUIDELINES.md):
  ✓ Retrieval MUST happen before generation
  ✓ LLM never answers without retrieved context
  ✓ Sources are always returned with the answer
  ✓ Hallucination reduced via grounded system prompt

Public API:
    rag_answer(question, n_context) -> RAGResponse
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

from ai.context_builder import ContextBlock, SourceRef, build_context
from ai.llm_adapter import get_llm
from search.hybrid_search import hybrid_search_all

logger = logging.getLogger("ai.rag")

DEFAULT_DB_PATH     = os.environ.get("SQLITE_DB_PATH", "db/travel.db")
DEFAULT_CHROMA_PATH = os.environ.get("CHROMA_DB_PATH", "db/chroma")

# System prompt — carefully crafted to ground the LLM in retrieved data
_SYSTEM_PROMPT_TEMPLATE = """\
You are a knowledgeable and friendly travel assistant for a travel company.

Your answers are STRICTLY grounded in the travel data provided below.
Do NOT invent packages, hotels, prices, or destinations that are not in the context.
If the context does not contain enough information to answer the question, say so clearly.

Travel Data Context:
{context}

Instructions:
- Answer concisely and helpfully in 2-5 sentences unless more detail is requested.
- Reference specific package names, hotel names, or destinations from the context.
- Suggest next steps (e.g., "You can explore the full itinerary for [Package Name]").
- Do not mention competitor brands or services not in the context.
- If a visa question is asked and the context includes visa requirements, summarise them clearly.
"""

_NO_CONTEXT_MESSAGE = (
    "I'm sorry, I couldn't find relevant travel information for your query. "
    "Please try rephrasing, or use the search to explore packages, hotels, and destinations."
)


@dataclass
class RAGResponse:
    """Full RAG answer with traceability metadata."""
    question: str
    answer: str
    sources: list[SourceRef] = field(default_factory=list)
    context_count: int = 0
    search_type: str = "hybrid"
    model: str = ""


def rag_answer(
    question: str,
    n_context: int = 10,
    db_path: str = DEFAULT_DB_PATH,
    chroma_path: str = DEFAULT_CHROMA_PATH,
) -> RAGResponse:
    """
    Run the full RAG pipeline for a travel question.

    Steps:
        1. Hybrid search to retrieve relevant context (ALWAYS first)
        2. Build structured context block from results
        3. If no context found — return graceful no-data message
        4. Call LLM with grounded system prompt + user question
        5. Return answer with full source references

    Args:
        question:    The traveller's natural language question
        n_context:   Number of results to retrieve per entity type
        db_path:     SQLite database path
        chroma_path: ChromaDB path

    Returns:
        RAGResponse with answer, sources, and metadata.
    """
    logger.info("RAG question: %r", question)

    # ── Step 1: Retrieve (ALWAYS before generation) ──────────────────────
    search_results = hybrid_search_all(
        query=question,
        db_path=db_path,
        chroma_path=chroma_path,
        n=n_context,
    )

    # ── Step 2: Build context block ───────────────────────────────────────
    context: ContextBlock = build_context(search_results)
    logger.info("Context built: %d sources, %d chars", context.count, len(context.text))

    # ── Step 3: Guard — no context = no LLM call ─────────────────────────
    if context.count == 0 or not context.text.strip():
        logger.warning("No context found for question: %r", question)
        return RAGResponse(
            question=question,
            answer=_NO_CONTEXT_MESSAGE,
            sources=[],
            context_count=0,
            search_type="hybrid",
        )

    # ── Step 4: Generate ─────────────────────────────────────────────────
    llm = get_llm()
    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(context=context.text)

    try:
        answer = llm.generate(system_prompt=system_prompt, user_message=question)
    except RuntimeError as exc:
        logger.error("LLM generation failed: %s", exc)
        # Return context summary as fallback (never leave user empty-handed)
        answer = (
            "I found relevant travel information but couldn't generate a full response. "
            "Please check the sources below for details."
        )

    # ── Step 5: Return with sources ───────────────────────────────────────
    return RAGResponse(
        question=question,
        answer=answer,
        sources=context.sources,
        context_count=context.count,
        search_type="hybrid",
        model=llm.model_name,
    )
