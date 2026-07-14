"""Health check router."""

from __future__ import annotations

from fastapi import APIRouter, Request

from api.schemas.health_schemas import DependencyStatus, HealthResponse
from config.constants import REPORT_SCHEMA_VERSION

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request) -> HealthResponse:
    dependencies = DependencyStatus(
        gemini=getattr(request.app.state, "gemini_status", "unknown"),
        qdrant=getattr(request.app.state, "qdrant_status", "unknown"),
        supabase=getattr(request.app.state, "supabase_status", "unknown"),
    )
    return HealthResponse(status="ok", version=REPORT_SCHEMA_VERSION, dependencies=dependencies)
