"""Shared foundational package for ArchMind AI.

Contains cross-cutting concerns with no business logic:
- shared/types/     — all internal data contract type definitions
- shared/exceptions/ — custom exception hierarchy per domain
- shared/logging/   — structured JSON logging

Dependency rule: shared/ imports only from config/ and stdlib/pydantic.
No module in shared/ imports from api/, core/, agents/, services/,
rag/, or infrastructure/.
"""
