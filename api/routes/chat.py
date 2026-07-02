"""
api/routes/chat.py
------------------
RAG Chatbot endpoint.

POST /chat
{
    "message": "What's the best package for a Goa honeymoon?",
    "n_context": 10
}

Response includes the LLM answer AND the source documents used,
so the traveller (and the system) can verify what data grounded the answer.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ai.rag_chain import rag_answer

logger = logging.getLogger("api.chat")

router = APIRouter(prefix="/chat", tags=["AI Travel Assistant"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="The traveller's question",
        examples=["What's the best honeymoon package in Goa?"],
    )
    n_context: int = Field(
        default=10,
        ge=1,
        le=30,
        description="Number of search results to use as context (default: 10)",
    )


class SourceRef(BaseModel):
    result_type: str
    title: str
    permalink: str = ""
    entity_id: str = ""


class ChatResponse(BaseModel):
    question: str
    answer: str
    sources: list[SourceRef] = Field(default_factory=list)
    context_count: int
    search_type: str
    model: str


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=ChatResponse,
    summary="AI Travel Assistant (RAG Chatbot)",
    description=(
        "Ask the AI travel assistant any travel question. "
        "Answers are grounded in real package, hotel, itinerary, and visa data "
        "retrieved via hybrid search — the LLM never invents information.\n\n"
        "**Examples:**\n"
        "- *What's the best honeymoon destination in India?*\n"
        "- *Tell me about trekking packages in Himachal Pradesh*\n"
        "- *What visa do I need for Singapore?*\n"
        "- *Suggest a 7-day wildlife safari itinerary*\n\n"
        "The `sources` field lists every document used to generate the answer."
    ),
)
def chat(request: ChatRequest) -> ChatResponse:
    """RAG chatbot — retrieve then generate, always."""
    logger.info("Chat request: %r (n_context=%d)", request.message, request.n_context)

    try:
        result = rag_answer(
            question=request.message,
            n_context=request.n_context,
        )
    except EnvironmentError as exc:
        # Missing API key — return actionable error
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc) + "\nRun 'python run_etl.py' and 'python run_ingest.py' first.",
        )
    except Exception as exc:
        logger.exception("Chat error: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Chat request failed. Check server logs.",
        )

    return ChatResponse(
        question=result.question,
        answer=result.answer,
        sources=[
            SourceRef(
                result_type=s.result_type,
                title=s.title,
                permalink=s.permalink,
                entity_id=s.entity_id,
            )
            for s in result.sources
        ],
        context_count=result.context_count,
        search_type=result.search_type,
        model=result.model,
    )
