# Project Guidelines

## Project Purpose

This project aims to build a Semantic Search and AI Travel Assistant for a travel company using data from a legacy travel website database export.

The objective is to allow users to search naturally using conversational language and receive highly relevant travel recommendations, itineraries, hotels, visa information, and destination suggestions.

---

# Development Philosophy

1. Prioritize working software over perfect software.
2. Prefer simple solutions over complex solutions.
3. Do not introduce new technologies unless there is a clear benefit.
4. Every architectural decision must be justified.
5. Maintain readability and maintainability.
6. Avoid premature optimization.
7. Client deadline is approximately one month.

---

# Architecture Principles

1. Separate ETL, Search, AI, and API layers.
2. Keep business logic independent from UI.
3. Keep vector database logic isolated.
4. Keep embedding generation modular.
5. Ensure future database migrations are possible.

---

# Data Handling Rules

1. Never modify original source files.
2. Always create processed copies.
3. Preserve IDs and relationships.
4. Preserve metadata whenever useful.
5. Remove HTML and presentation formatting.
6. Normalize whitespace and encoding issues.
7. Log all transformations.

---

# AI Search Rules

1. Search quality is more important than chatbot quality.
2. Retrieval must happen before generation.
3. Never allow the LLM to answer without retrieved context.
4. Reduce hallucinations whenever possible.
5. Return sources used for answers.
6. Maintain metadata references for traceability.

---

# Embedding Rules

Preferred Model:
all-MiniLM-L6-v2

Do not change embedding models without justification.

Store embeddings separately from raw data.

---

# Vector Database Rules

Preferred Database:
ChromaDB

Do not introduce Pinecone, Weaviate, Milvus, or other vector databases unless scalability requirements justify it.

---

# Backend Rules

Preferred Framework:
FastAPI

Requirements:

* Type hints
* Modular structure
* Environment variables
* Logging
* Error handling

---

# Code Quality Rules

1. Follow PEP8.
2. Use meaningful names.
3. Avoid duplicated code.
4. Create reusable functions.
5. Add comments only where necessary.
6. Prefer clarity over cleverness.

---

# API Rules

All endpoints must:

* Validate input
* Return structured responses
* Handle failures gracefully
* Include documentation

---

# Security Rules

1. Never hardcode API keys.
2. Never expose secrets.
3. Use environment variables.
4. Validate user input.
5. Sanitize search requests.

---

# Performance Rules

1. Build MVP first.
2. Measure before optimizing.
3. Optimize bottlenecks only after identification.

---

# AI Assistant Behaviour

Before making changes:

1. Understand existing architecture.
2. Review Guidelines.md.
3. Explain reasoning.
4. Identify risks.
5. Propose implementation plan.
6. Then write code.

Never make large architectural changes without explaining them first.

---

# Deliverable Priority

Priority 1:
Data Extraction and Cleaning

Priority 2:
Semantic Search

Priority 3:
Search API

Priority 4:
Travel Recommendation Engine

Priority 5:
RAG Chatbot

Priority 6:
Frontend Enhancements

Chatbot is not the first milestone.

Search quality is the first milestone.
