"""API response schema for the health check endpoint."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DependencyStatus(BaseModel):
    """Startup probe results for each external dependency.

    Each field holds one of: "ok", "failed", "unreachable",
    "collection_missing", or "unknown" (reported before probes complete or
    when the server runs without a lifespan, e.g. in isolated unit tests).
    """

    gemini: str = Field(..., description="Gemini API probe result.")
    qdrant: str = Field(
        ...,
        description=(
            "Qdrant probe result. 'collection_missing' means Qdrant is reachable "
            "but the knowledge base collection has not been loaded."
        ),
    )
    supabase: str = Field(..., description="Supabase probe result.")


def _default_dependency_status() -> DependencyStatus:
    return DependencyStatus(gemini="unknown", qdrant="unknown", supabase="unknown")


class HealthResponse(BaseModel):
    """Response body for GET /health.

    `status` represents application health — "ok" means the server is up and
    accepting requests. It does NOT reflect dependency state.

    `dependencies` represents individual dependency probe results captured at
    startup. A degraded dependency does NOT change `status` or the HTTP 200
    response code. The server continues to serve requests even if one or more
    dependencies are degraded.

    Example response when Gemini is unavailable:
        {
            "status": "ok",
            "version": "1.0",
            "dependencies": {
                "gemini": "failed",
                "qdrant": "ok",
                "supabase": "ok"
            }
        }
    """

    status: str = Field(
        ...,
        description="Application health. 'ok' when the server is up and accepting requests.",
    )
    version: str = Field(..., description="Application version string.")
    dependencies: DependencyStatus = Field(
        default_factory=_default_dependency_status,
        description="Startup probe results for each external dependency.",
    )
