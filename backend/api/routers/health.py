"""Health check router."""

from __future__ import annotations

from fastapi import APIRouter

from api.schemas.health_schemas import HealthResponse
from config.constants import REPORT_SCHEMA_VERSION

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(status="ok", version=REPORT_SCHEMA_VERSION)
