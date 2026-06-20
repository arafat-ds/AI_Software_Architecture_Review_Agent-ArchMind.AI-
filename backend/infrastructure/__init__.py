"""Infrastructure layer.

Thin wrappers around external services. Contains no business logic.

- gemini_client.py  — Google Gemini API (text generation + embeddings)
- qdrant_client.py  — Qdrant vector store (upsert + search)
- supabase_client.py — Supabase Postgres (job records + report persistence)
"""
