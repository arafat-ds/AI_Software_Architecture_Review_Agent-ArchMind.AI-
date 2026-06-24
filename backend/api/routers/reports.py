"""Reports router: retrieve generated analysis reports.

get_supabase_client raises NotImplementedError by default. Override via
app.dependency_overrides in tests or api/dependencies.py in production.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from api.schemas.report_schemas import ReportResponse
from infrastructure.supabase_client import SupabaseClient

router = APIRouter(tags=["reports"])


def get_supabase_client() -> SupabaseClient:
    raise NotImplementedError("Provide via app.dependency_overrides or api/dependencies.py.")


@router.get("/reports/{report_id}", response_model=ReportResponse)
async def get_report(
    report_id: UUID,
    supabase: SupabaseClient = Depends(get_supabase_client),
) -> ReportResponse:
    raw = supabase.get_report(report_id)
    if raw is None:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found.")
    return ReportResponse.model_validate(raw)
