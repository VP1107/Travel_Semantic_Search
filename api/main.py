"""
api/main.py
-----------
FastAPI application entry point for the Travel Search API.

Start with:
    uvicorn api.main:app --reload

Or via uvicorn programmatically:
    python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
"""

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import chat, hotels, hybrid, packages, search, semantic, visa

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("api")

# ---------------------------------------------------------------------------
# App definition
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Travel Search API",
    description=(
        "Semantic keyword search across travel packages, hotels, "
        "itineraries, and visa information. "
        "Powered by SQLite FTS5 with BM25 ranking."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
# Allow all origins in development. Restrict to your frontend domain in prod.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server (frontend)
        "http://localhost:3000",   # Alternative React dev port
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(search.router)
app.include_router(semantic.router)
app.include_router(hybrid.router)
app.include_router(packages.router)
app.include_router(hotels.router)
app.include_router(visa.router)
app.include_router(chat.router)


# ---------------------------------------------------------------------------
# Root endpoint
# ---------------------------------------------------------------------------
@app.get("/", tags=["Health"], summary="API health check")
def root() -> dict:
    """Returns API status and list of available endpoints."""
    db_path = os.environ.get("SQLITE_DB_PATH", "db/travel.db")
    db_exists = os.path.exists(db_path)
    return {
        "status": "ok",
        "api": "Travel Search API",
        "version": "1.0.0",
        "database": {
            "path": db_path,
            "ready": db_exists,
        },
        "endpoints": {
            "keyword_search":  "GET  /search?q=<query>",
            "semantic_search": "GET  /search/semantic?q=<query>",
            "hybrid_search":   "GET  /search/hybrid?q=<query>",
            "ai_chat":         "POST /chat",
            "packages":  "GET /packages  |  GET /packages/{id}",
            "hotels":    "GET /hotels    |  GET /hotels/{id}",
            "visa":      "GET /visa      |  GET /visa/{country}",
            "docs":      "GET /docs",
        },
    }
