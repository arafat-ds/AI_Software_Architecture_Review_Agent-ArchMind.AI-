"""Jobs router: submit analysis jobs and poll for status.

Dependency stubs (get_orchestrator, get_executor, get_supabase_client) raise
NotImplementedError by default. Override via app.dependency_overrides in tests
or replace with real implementations from api/dependencies.py in production.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException

from api.schemas.job_schemas import JobStatusResponse, JobSubmittedResponse, SubmitJobRequest
from infrastructure.supabase_client import SupabaseClient
from services.orchestrator import AnalysisOrchestrator

router = APIRouter(tags=["jobs"])


def get_supabase_client() -> SupabaseClient:
    raise NotImplementedError("Provide via app.dependency_overrides or api/dependencies.py.")


def get_orchestrator() -> AnalysisOrchestrator:
    raise NotImplementedError("Provide via app.dependency_overrides or api/dependencies.py.")


def get_executor() -> ThreadPoolExecutor:
    raise NotImplementedError("Provide via app.dependency_overrides or api/dependencies.py.")


@router.post("/jobs", status_code=202, response_model=JobSubmittedResponse)
async def submit_job(
    request: SubmitJobRequest,
    orchestrator: AnalysisOrchestrator = Depends(get_orchestrator),
    executor: ThreadPoolExecutor = Depends(get_executor),
) -> JobSubmittedResponse:
    job_id = uuid4()
    raw_name = request.repo_url.rstrip("/").split("/")[-1]
    repo_name = raw_name.removesuffix(".git")
    orchestrator.create_job(job_id, request.repo_url, repo_name)
    executor.submit(orchestrator.run, job_id, request.repo_url)
    return JobSubmittedResponse(
        job_id=job_id,
        status="PENDING",
        message="Analysis queued. Poll GET /jobs/{job_id} for status.",
    )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: UUID,
    supabase: SupabaseClient = Depends(get_supabase_client),
) -> JobStatusResponse:
    raw = supabase.get_job(job_id)
    if raw is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    return JobStatusResponse.model_validate(raw)
