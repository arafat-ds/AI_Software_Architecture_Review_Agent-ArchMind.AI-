"""API response schema for the health check endpoint."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Response body for GET /health."""

    status: str = Field(..., description="Service status. 'ok' when healthy.")
    version: str = Field(..., description="Application version string.")
